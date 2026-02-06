import 'dart:typed_data';

import 'package:share_plus/share_plus.dart';

Future<XFile> buildShareXFile(Uint8List bytes) async {
  return XFile.fromData(
    bytes,
    mimeType: 'image/png',
    name: 'olala_result.png',
  );
}
