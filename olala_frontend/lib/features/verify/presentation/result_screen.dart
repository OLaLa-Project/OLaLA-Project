import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'result_controller.dart';

class ResultScreen extends GetView<ResultController> {
  const ResultScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Obx(() => Text(controller.isLoading.value ? '검증 진행 중' : '검증 결과')),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: controller.goBack,
        ),
      ),
      body: Obx(() {
        if (controller.isLoading.value) {
          return _buildLogListView();
        }

        if (controller.finalResult.value == null) {
          return const Center(child: Text('결과를 불러올 수 없습니다.'));
        }

        return _buildResultView(context);
      }),
    );
  }

  Widget _buildLogListView() {
    return Column(
      children: [
        if (controller.isLoading.value) ...[
          const LinearProgressIndicator(),
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Text('각 단계를 클릭하여 상세 내용을 확인할 수 있습니다.',
              style: TextStyle(color: Colors.grey, fontSize: 12)),
          ),
        ],
        Expanded(
          child: Obx(() {
            final logs = controller.logs;
            if (logs.isEmpty) {
              return const Center(child: Text('로그 대기 중...'));
            }
            return ListView.builder(
              itemCount: logs.length,
              itemBuilder: (context, index) {
                final log = logs[index];
                return _buildLogTile(log);
              },
            );
          }),
        ),
      ],
    );
  }

  Widget _buildLogTile(StageLog log) {
    if (log.data.isEmpty) {
      return ListTile(
        leading: const Icon(Icons.check_circle_outline, size: 20, color: Colors.green),
        title: Text(log.label),
        subtitle: Text(log.stage, style: const TextStyle(fontSize: 10, color: Colors.grey)),
      );
    }

    return ExpansionTile(
      leading: const Icon(Icons.check_circle, size: 20, color: Colors.green),
      title: Text(log.label),
      subtitle: Text(log.stage, style: const TextStyle(fontSize: 10, color: Colors.grey)),
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          color: Colors.grey[50],
          child: _buildStageDetail(log),
        ),
      ],
    );
  }

  Widget _buildStageDetail(StageLog log) {
    // Custom View for Stage 1 (Transcript)
    if (log.stage == 'stage01_normalize' && log.data.containsKey('transcript')) {
       final transcript = log.data['transcript'] as String?;
       if (transcript != null && transcript.isNotEmpty) {
         return Column(
           crossAxisAlignment: CrossAxisAlignment.start,
           children: [
             const Text('영상 자막 추출 결과:', style: TextStyle(fontWeight: FontWeight.bold)),
             const SizedBox(height: 8),
             Container(
               padding: const EdgeInsets.all(12),
               decoration: BoxDecoration(
                 color: Colors.white,
                 border: Border.all(color: Colors.grey[300]!),
                 borderRadius: BorderRadius.circular(4),
               ),
               constraints: const BoxConstraints(maxHeight: 200),
               child: SingleChildScrollView(
                 child: Text(transcript, style: const TextStyle(fontSize: 12)),
               ),
             ),
             const SizedBox(height: 12),
             const Text('추출된 주장:', style: TextStyle(fontWeight: FontWeight.bold)),
             Text(log.data['claim_text'] ?? '-'),
           ],
         );
       }
    }

    // Custom View for Stage 3 (Evidence)
    if (log.stage.contains('stage03') || log.stage == 'stage05_topk') {
      List candidates = [];
      if (log.data.containsKey('wiki_candidates')) candidates = log.data['wiki_candidates'];
      else if (log.data.containsKey('web_candidates')) candidates = log.data['web_candidates'];
      else if (log.data.containsKey('evidence_candidates')) candidates = log.data['evidence_candidates'];
      else if (log.data.containsKey('evidence_topk')) candidates = log.data['evidence_topk'];

      if (candidates.isNotEmpty) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('수집된 증거 (${candidates.length}건)', style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            ...candidates.map((c) => Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('• ${c['title'] ?? '제목 없음'}', style: const TextStyle(fontSize: 14)),
                  Text(c['url'] ?? '', style: const TextStyle(fontSize: 11, color: Colors.blue)),
                  if (c['snippet'] != null) Text(c['snippet'].toString().trim().replaceAll('\n', ' ').substring(0, c['snippet'].toString().length > 50 ? 50 : null) + '...', style: const TextStyle(fontSize: 11, color: Colors.grey)),
                ],
              ),
            )).toList()
          ],
        );
      }
    }
    
    // Custom View for Stage 2 (Queries)
    if (log.stage == 'stage02_querygen' && log.data.containsKey('query_variants')) {
       final queries = log.data['query_variants'] as List;
       return Column(
         crossAxisAlignment: CrossAxisAlignment.start,
         children: [
           const Text('생성된 검색어:', style: TextStyle(fontWeight: FontWeight.bold)),
           ...queries.map((q) => Text('- ${q['text']}')).toList(),
         ],
       );
    }

    // Default JSON View
    const JsonEncoder encoder = JsonEncoder.withIndent('  ');
    return SelectableText(
      encoder.convert(log.data),
      style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
    );
  }

  Widget _buildResultView(BuildContext context) {
    final result = controller.finalResult.value!;
    return DefaultTabController(
      length: 2,
      child: Column(
        children: [
          const TabBar(tabs: [
            Tab(text: '최종 결과'),
            Tab(text: '상세 과정'),
          ]),
          Expanded(
            child: TabBarView(
              children: [
                SingleChildScrollView(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildVerdictCard(result),
                      const SizedBox(height: 24),
                      const Text('요약', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      Text(result.summary, style: const TextStyle(fontSize: 15)),
                      const SizedBox(height: 24),
                      if (result.rationale.isNotEmpty) ...[
                        const Text('판정 근거', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        ...result.rationale.map((r) => Padding(
                          padding: const EdgeInsets.only(bottom: 6.0),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('• ', style: TextStyle(fontSize: 16)),
                              Expanded(child: Text(r)),
                            ],
                          ),
                        )),
                      ],
                    ],
                  ),
                ),
                _buildLogListView(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVerdictCard(result) {
    Color color = Colors.grey;
    if (result.label == 'TRUE') color = Colors.green;
    if (result.label == 'FALSE') color = Colors.red;
    if (result.label == 'MIXED') color = Colors.orange;

    return Card(
      color: color,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(result.label, style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
                  Text('신뢰도: ${(result.confidence * 100).toStringAsFixed(1)}%', style: const TextStyle(color: Colors.white70)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
