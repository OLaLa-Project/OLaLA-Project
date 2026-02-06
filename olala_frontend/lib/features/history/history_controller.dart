import 'package:get/get.dart';
import 'package:get_storage/get_storage.dart';
import 'models/history_item.dart';

class HistoryController extends GetxController {
  final _box = GetStorage();
  final items = <HistoryItem>[].obs;
  
  static const String _storageKey = 'verification_history';

  @override
  void onInit() {
    super.onInit();
    _loadItems();
  }

  void _loadItems() {
    final List<dynamic>? stored = _box.read<List<dynamic>>(_storageKey);
    if (stored != null) {
      items.assignAll(stored.map((e) => HistoryItem.fromJson(e)).toList());
    }
  }

  void saveItem(HistoryItem item) {
    // Add to top of list
    items.insert(0, item);
    
    // Persist
    _saveToStorage();
  }

  void removeById(String id) {
    items.removeWhere((e) => e.id == id);
    _saveToStorage();
  }

  void clearAll() {
    items.clear();
    _box.remove(_storageKey);
  }

  void _saveToStorage() {
    final jsonList = items.map((e) => e.toJson()).toList();
    _box.write(_storageKey, jsonList);
  }
}

