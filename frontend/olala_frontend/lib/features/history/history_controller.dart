import 'package:get/get.dart';
import 'models/history_item.dart';

class HistoryController extends GetxController {
  // MVP: 메모리 저장 (추후 local_storage로 교체)
  final items = <HistoryItem>[].obs;

  @override
  void onInit() {
    super.onInit();

    // ✅ 데모 데이터 (Result 연결 전 임시)
    if (items.isEmpty) {
      items.addAll(List.generate(8, (i) {
        return HistoryItem(
          id: 'h_$i',
          inputSummary: '예) https://example.com/news/${100 + i}',
          resultLabel: i % 3 == 0 ? 'TRUE' : (i % 3 == 1 ? 'FALSE' : 'MIXED'),
          timestamp: DateTime.now().subtract(Duration(minutes: i * 12)),
        );
      }));
    }
  }

  void removeById(String id) {
    items.removeWhere((e) => e.id == id);
  }

  void clearAll() {
    items.clear();
  }
}

