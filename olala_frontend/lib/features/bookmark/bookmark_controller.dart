import 'package:get/get.dart';
import 'models/bookmark_item.dart';

class BookmarkController extends GetxController {
  final items = <BookmarkItem>[].obs;

  @override
  void onInit() {
    super.onInit();

    // ✅ 데모 데이터(추후 실제 북마크 저장소로 대체)
    if (items.isEmpty) {
      items.addAll(List.generate(6, (i) {
        return BookmarkItem(
          id: 'b_$i',
          inputSummary: '예) 사용자가 북마크한 입력 ${i + 1}',
          resultLabel: i % 2 == 0 ? 'TRUE' : 'FALSE',
          timestamp: DateTime.now().subtract(Duration(hours: i * 3)),
        );
      }));
    }
  }

  void toggleOff(String id) {
    items.removeWhere((e) => e.id == id);
  }
}
