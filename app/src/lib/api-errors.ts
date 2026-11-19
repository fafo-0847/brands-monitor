export class NotConfiguredError extends Error {
  constructor() {
    super('The app is not connected to a database yet.');
  }
}
