import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

Future<XFile> buildShareXFile(Uint8List bytes) async {
  final directory = await getTemporaryDirectory();
  final imagePath =
      '${directory.path}/olala_result_${DateTime.now().millisecondsSinceEpoch}.png';
  final imageFile = File(imagePath);

  await imageFile.writeAsBytes(bytes);
  return XFile(imageFile.path);
}
