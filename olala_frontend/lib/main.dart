import 'package:flutter/material.dart';
import 'app/app.dart';
import 'shared/storage/local_storage.dart';
import 'package:get_storage/get_storage.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await GetStorage.init(); // Initialize GetStorage for history


  // ✅ 강제 초기화 (테스트용 - 한 번 실행 후 주석 처리하세요!)
  await LocalStorage.clearAll();

  runApp(const OLaLAApp());
}
