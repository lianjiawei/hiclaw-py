import type { PixelOfficeCommand } from './types.js';
import { PixelOfficeController } from './pixelOffice.js';

export function dispatchJsonCommand(controller: PixelOfficeController, payload: string | PixelOfficeCommand): void {
  if (typeof payload === 'string') {
    controller.dispatchJson(payload);
    return;
  }
  controller.dispatch(payload);
}

export function bindWebSocketCommandStream(controller: PixelOfficeController, socket: Pick<WebSocket, 'addEventListener'>): void {
  socket.addEventListener('message', (event: MessageEvent<string>) => {
    if (typeof event.data !== 'string') return;
    controller.dispatchJson(event.data);
  });
}
