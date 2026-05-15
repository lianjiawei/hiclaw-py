import type { PixelOfficeCommand } from './types.js';
import { PixelOfficeController } from './pixelOffice.js';
export declare function dispatchJsonCommand(controller: PixelOfficeController, payload: string | PixelOfficeCommand): void;
export declare function bindWebSocketCommandStream(controller: PixelOfficeController, socket: Pick<WebSocket, 'addEventListener'>): void;
