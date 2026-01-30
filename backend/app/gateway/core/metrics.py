"""
Gateway Metrics Collection.

Gateway 작업의 메트릭을 수집하고 관리합니다.

Features:
- 성공/실패 카운터
- 레이턴시 히스토그램
- Circuit breaker 상태 추적
- 메트릭 내보내기 (JSON, Prometheus 형식)
"""

import time
import threading
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """단일 작업 메트릭."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    last_call_time: Optional[float] = None
    last_error: Optional[str] = None

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float("inf") else 0,
            "max_latency_ms": round(self.max_latency_ms, 2),
            "last_call_time": self.last_call_time,
            "last_error": self.last_error,
        }


@dataclass
class GatewayMetrics:
    """Gateway 전체 메트릭."""

    gateway_name: str
    operations: Dict[str, OperationMetrics] = field(default_factory=dict)
    circuit_open_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "gateway_name": self.gateway_name,
            "operations": {k: v.to_dict() for k, v in self.operations.items()},
            "circuit_open_count": self.circuit_open_count,
            "uptime_seconds": round(time.time() - self.created_at, 2),
            "created_at": datetime.fromtimestamp(
                self.created_at, tz=timezone.utc
            ).isoformat(),
        }


class MetricsCollector:
    """
    메트릭 수집기.

    사용 예:
        metrics = MetricsCollector()

        # 성공 기록
        start = time.time()
        result = call_service()
        latency_ms = (time.time() - start) * 1000
        metrics.record_success("llm", "generate", latency_ms)

        # 실패 기록
        metrics.record_failure("llm", "generate", latency_ms, "timeout")

        # 메트릭 조회
        stats = metrics.get_metrics()
    """

    def __init__(self):
        self._gateways: Dict[str, GatewayMetrics] = {}
        self._lock = threading.RLock()
        self._latency_buckets: Dict[str, List[float]] = defaultdict(list)
        self._max_bucket_size = 1000  # 최근 1000개 레이턴시 유지

    def _get_or_create_gateway(self, gateway_name: str) -> GatewayMetrics:
        """Gateway 메트릭 가져오기 또는 생성."""
        if gateway_name not in self._gateways:
            self._gateways[gateway_name] = GatewayMetrics(gateway_name=gateway_name)
        return self._gateways[gateway_name]

    def _get_or_create_operation(
        self, gateway_name: str, operation_name: str
    ) -> OperationMetrics:
        """Operation 메트릭 가져오기 또는 생성."""
        gateway = self._get_or_create_gateway(gateway_name)
        if operation_name not in gateway.operations:
            gateway.operations[operation_name] = OperationMetrics()
        return gateway.operations[operation_name]

    def record_success(
        self,
        gateway_name: str,
        operation_name: str,
        latency_ms: float,
    ) -> None:
        """성공 기록."""
        with self._lock:
            op = self._get_or_create_operation(gateway_name, operation_name)
            op.total_calls += 1
            op.successful_calls += 1
            op.total_latency_ms += latency_ms
            op.min_latency_ms = min(op.min_latency_ms, latency_ms)
            op.max_latency_ms = max(op.max_latency_ms, latency_ms)
            op.last_call_time = time.time()

            # 레이턴시 버킷에 추가
            bucket_key = f"{gateway_name}:{operation_name}"
            self._latency_buckets[bucket_key].append(latency_ms)
            if len(self._latency_buckets[bucket_key]) > self._max_bucket_size:
                self._latency_buckets[bucket_key] = self._latency_buckets[bucket_key][
                    -self._max_bucket_size :
                ]

        logger.debug(
            f"Metrics: {gateway_name}.{operation_name} success, "
            f"latency={latency_ms:.2f}ms"
        )

    def record_failure(
        self,
        gateway_name: str,
        operation_name: str,
        latency_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """실패 기록."""
        with self._lock:
            op = self._get_or_create_operation(gateway_name, operation_name)
            op.total_calls += 1
            op.failed_calls += 1
            op.last_call_time = time.time()
            op.last_error = error

        logger.debug(
            f"Metrics: {gateway_name}.{operation_name} failure, "
            f"latency={latency_ms:.2f}ms, error={error}"
        )

    def record_circuit_open(
        self,
        gateway_name: str,
        operation_name: str,
    ) -> None:
        """Circuit breaker OPEN 기록."""
        with self._lock:
            gateway = self._get_or_create_gateway(gateway_name)
            gateway.circuit_open_count += 1

        logger.warning(
            f"Metrics: {gateway_name}.{operation_name} circuit open "
            f"(total opens: {gateway.circuit_open_count})"
        )

    def get_metrics(self, gateway_name: Optional[str] = None) -> dict:
        """
        메트릭 조회.

        Args:
            gateway_name: 특정 gateway만 조회 (None이면 전체)

        Returns:
            메트릭 딕셔너리
        """
        with self._lock:
            if gateway_name:
                if gateway_name in self._gateways:
                    return self._gateways[gateway_name].to_dict()
                return {}

            return {
                "gateways": {
                    name: gw.to_dict() for name, gw in self._gateways.items()
                },
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_latency_percentiles(
        self,
        gateway_name: str,
        operation_name: str,
        percentiles: List[float] = None,
    ) -> Dict[str, float]:
        """
        레이턴시 백분위수 계산.

        Args:
            gateway_name: Gateway 이름
            operation_name: 작업 이름
            percentiles: 계산할 백분위수 (기본: [50, 90, 95, 99])

        Returns:
            백분위수 딕셔너리
        """
        if percentiles is None:
            percentiles = [50, 90, 95, 99]

        bucket_key = f"{gateway_name}:{operation_name}"

        with self._lock:
            latencies = self._latency_buckets.get(bucket_key, [])
            if not latencies:
                return {f"p{p}": 0.0 for p in percentiles}

            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)

            result = {}
            for p in percentiles:
                idx = int((p / 100) * n)
                idx = min(idx, n - 1)
                result[f"p{p}"] = round(sorted_latencies[idx], 2)

            return result

    def reset(self, gateway_name: Optional[str] = None) -> None:
        """
        메트릭 리셋.

        Args:
            gateway_name: 특정 gateway만 리셋 (None이면 전체)
        """
        with self._lock:
            if gateway_name:
                if gateway_name in self._gateways:
                    self._gateways[gateway_name] = GatewayMetrics(
                        gateway_name=gateway_name
                    )
                    # 관련 레이턴시 버킷도 삭제
                    keys_to_delete = [
                        k for k in self._latency_buckets if k.startswith(f"{gateway_name}:")
                    ]
                    for k in keys_to_delete:
                        del self._latency_buckets[k]
            else:
                self._gateways.clear()
                self._latency_buckets.clear()

        logger.info(f"Metrics reset: {gateway_name or 'all'}")

    def to_prometheus_format(self) -> str:
        """Prometheus 형식으로 메트릭 내보내기."""
        lines = []

        with self._lock:
            for gw_name, gw in self._gateways.items():
                for op_name, op in gw.operations.items():
                    labels = f'gateway="{gw_name}",operation="{op_name}"'

                    lines.append(
                        f"gateway_calls_total{{{labels}}} {op.total_calls}"
                    )
                    lines.append(
                        f"gateway_calls_success{{{labels}}} {op.successful_calls}"
                    )
                    lines.append(
                        f"gateway_calls_failed{{{labels}}} {op.failed_calls}"
                    )
                    lines.append(
                        f"gateway_latency_avg_ms{{{labels}}} {op.avg_latency_ms:.2f}"
                    )
                    if op.min_latency_ms != float("inf"):
                        lines.append(
                            f"gateway_latency_min_ms{{{labels}}} {op.min_latency_ms:.2f}"
                        )
                    lines.append(
                        f"gateway_latency_max_ms{{{labels}}} {op.max_latency_ms:.2f}"
                    )

                lines.append(
                    f'gateway_circuit_open_total{{gateway="{gw_name}"}} {gw.circuit_open_count}'
                )

        return "\n".join(lines)


# 전역 메트릭 수집기 인스턴스
_global_metrics: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_global_metrics() -> MetricsCollector:
    """전역 메트릭 수집기 반환."""
    global _global_metrics
    with _metrics_lock:
        if _global_metrics is None:
            _global_metrics = MetricsCollector()
        return _global_metrics
