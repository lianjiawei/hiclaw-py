import { OfficeState } from './officeState.js';
import type { PixelOfficeAssetBundle, PixelOfficeCommand, PixelOfficeEventMap } from './types.js';
export interface PixelOfficeOptions {
    zoom?: number;
    autoResize?: boolean;
}
type Listener<K extends keyof PixelOfficeEventMap> = (payload: PixelOfficeEventMap[K]) => void;
export declare class PixelOfficeController {
    readonly canvas: HTMLCanvasElement;
    readonly officeState: OfficeState;
    private container;
    private stopLoop;
    private resizeObserver;
    private listeners;
    private offset;
    private pan;
    zoom: number;
    constructor(container: HTMLElement, options?: PixelOfficeOptions);
    loadAssets(bundle: PixelOfficeAssetBundle): void;
    setLayout(layout: Parameters<OfficeState['setLayout']>[0]): void;
    dispatch(command: PixelOfficeCommand): void;
    dispatchJson(commandJson: string): void;
    on<K extends keyof PixelOfficeEventMap>(eventName: K, listener: Listener<K>): () => void;
    destroy(): void;
    private resizeCanvas;
    private bindCanvasEvents;
    private emit;
    private getListenerBucket;
    private screenToWorld;
    private hitTestAgent;
    private updateCameraFollow;
}
export {};
