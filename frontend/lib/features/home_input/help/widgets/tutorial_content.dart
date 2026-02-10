import 'package:flutter/foundation.dart';

/// Help(코치마크)에서 하이라이트할 타겟들
enum GuideTarget {
  settings,
  inputTypeSelector,
  inputField,
  inputClearButton,
  verifyStartButton,
  navHistory,
  navVerify,
  navBookmark,
}

/// 라벨을 어느 방향에 둘지(샘플 앱들처럼 곡선 라인으로 연결)
enum LabelPlacement {
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
  left,
  right,
  top,
  bottom,
}

@immutable
class GuideItem {
  final GuideTarget target;
  final String title;
  final String description;
  final LabelPlacement placement;

  const GuideItem({
    required this.target,
    required this.title,
    required this.description,
    required this.placement,
  });
}

class TutorialContent {
  /// HomeInput 한 페이지(상단 설정 + 입력 4 + 하단바 3)
  static const List<GuideItem> homeInputGuideItems = [
    GuideItem(
      target: GuideTarget.settings,
      title: '설정',
      description: '환경설정/알림/약관 등을 여기서 확인할 수 있어요.',
      placement: LabelPlacement.bottomLeft,
    ),
    GuideItem(
      target: GuideTarget.inputTypeSelector,
      title: '입력 방식 선택',
      description: 'URL / 텍스트 중 검증할 입력 유형을 선택해요.',
      placement: LabelPlacement.bottomLeft,
    ),
    GuideItem(
      target: GuideTarget.inputField,
      title: '입력창',
      description: '검증할 URL 또는 문장을 붙여넣거나 입력해요.',
      placement: LabelPlacement.topLeft,
    ),
    GuideItem(
      target: GuideTarget.inputClearButton,
      title: '입력 초기화',
      description: 'X 버튼을 누르면 입력창 내용을 한 번에 지울 수 있어요.',
      placement: LabelPlacement.topRight,
    ),
    GuideItem(
      target: GuideTarget.verifyStartButton,
      title: '검증 시작',
      description: '입력이 준비되면 눌러서 검증을 시작해요.',
      placement: LabelPlacement.top,
    ),
    GuideItem(
      target: GuideTarget.navHistory,
      title: '히스토리',
      description: '최근 검증 결과를 다시 확인할 수 있어요.',
      placement: LabelPlacement.topLeft,
    ),
    GuideItem(
      target: GuideTarget.navVerify,
      title: '검증',
      description: '현재 화면(검증 입력)으로 돌아오는 탭이에요.',
      placement: LabelPlacement.top,
    ),
    GuideItem(
      target: GuideTarget.navBookmark,
      title: '북마크',
      description: '저장한 결과를 모아볼 수 있어요.',
      placement: LabelPlacement.topRight,
    ),
  ];
}
