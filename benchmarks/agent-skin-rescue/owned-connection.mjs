// Small ownership scope used by the disabled R10 recovery copy and synthetic tests.
export async function withOwnedSocket(open, work) {
  let socket;
  let value;
  let primary;
  let cleanup;
  let workFailed = false;
  let cleanupFailed = false;
  try {
    socket = await open();
    value = await work(socket);
  } catch (error) {
    primary = error;
    workFailed = true;
  } finally {
    if (socket) {
      try { await socket.close(); }
      catch (error) { cleanup = error; cleanupFailed = true; }
    }
  }
  if (workFailed && cleanupFailed) throw new AggregateError([primary, cleanup], 'work-failed-and-cleanup-unknown');
  if (workFailed) throw primary;
  if (cleanupFailed) throw new AggregateError([cleanup], 'cleanup-unknown');
  return value;
}
