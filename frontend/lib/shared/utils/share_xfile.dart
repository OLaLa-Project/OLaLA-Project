import 'dart:typed_data';

import 'package:share_plus/share_plus.dart';

import 'share_xfile_stub.dart'
    if (dart.library.html) 'share_xfile_web.dart'
    if (dart.library.io) 'share_xfile_io.dart' as impl;

Future<XFile> buildShareXFile(Uint8List bytes) => impl.buildShareXFile(bytes);
