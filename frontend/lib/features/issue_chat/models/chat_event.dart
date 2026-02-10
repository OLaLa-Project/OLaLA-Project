class ChatEventType {
  // Client -> Server
  static const String join = 'join';
  static const String messageCreate = 'message.create';
  static const String reactionToggle = 'reaction.toggle';

  // Server -> Client
  static const String messageCreated = 'message.created';
  static const String messageAck = 'message.ack';
  static const String reactionUpdated = 'reaction.updated';
  static const String presence = 'presence';
  static const String error = 'error';

  // Internal connection events
  static const String connectionConnecting = 'connection.connecting';
  static const String connectionOpen = 'connection.open';
  static const String connectionClosed = 'connection.closed';
  static const String connectionError = 'connection.error';
}
