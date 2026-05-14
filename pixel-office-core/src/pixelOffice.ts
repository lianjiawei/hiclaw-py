import { CAMERA_FOLLOW_LERP, CAMERA_FOLLOW_SNAP_THRESHOLD, PAN_MARGIN_FRACTION, TILE_SIZE } from './constants.js';
import { applyAssetBundle } from './browserAssetLoader.js';
import { startGameLoop } from './gameLoop.js';
import { OfficeState } from './officeState.js';
import { renderFrame } from './renderer.js';
import type { PixelOfficeAssetBundle, PixelOfficeCommand, PixelOfficeEventMap } from './types.js';

export interface PixelOfficeOptions {
  zoom?: number;
  autoResize?: boolean;
}

type Listener<K extends keyof PixelOfficeEventMap> = (payload: PixelOfficeEventMap[K]) => void;

export class PixelOfficeController {
  readonly canvas: HTMLCanvasElement;
  readonly officeState: OfficeState;

  private container: HTMLElement;
  private stopLoop: (() => void) | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private listeners: Partial<Record<keyof PixelOfficeEventMap, Array<(payload: unknown) => void>>> = {};
  private offset = { x: 0, y: 0 };
  private pan = { x: 0, y: 0 };
  zoom: number;

  constructor(container: HTMLElement, options: PixelOfficeOptions = {}) {
    this.container = container;
    this.canvas = document.createElement('canvas');
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.display = 'block';
    this.container.appendChild(this.canvas);
    this.officeState = new OfficeState();
    this.zoom = options.zoom ?? 2;
    this.bindCanvasEvents();
    this.resizeCanvas();
    if (options.autoResize !== false) {
      this.resizeObserver = new ResizeObserver(() => this.resizeCanvas());
      this.resizeObserver.observe(this.container);
    }
    this.stopLoop = startGameLoop(this.canvas, {
      update: (dt) => {
        this.officeState.update(dt);
      },
      render: (ctx) => {
        if (this.officeState.cameraFollowId !== null) this.updateCameraFollow();
        const result = renderFrame(
          ctx,
          this.canvas.width,
          this.canvas.height,
          this.officeState.tileMap,
          this.officeState.furniture,
          this.officeState.getCharacters(),
          this.zoom,
          this.pan.x,
          this.pan.y,
          this.officeState.getLayout().tileColors,
          this.officeState.getLayout().cols,
          this.officeState.getLayout().rows,
        );
        this.offset = { x: result.offsetX, y: result.offsetY };
      },
    });
  }

  loadAssets(bundle: PixelOfficeAssetBundle): void {
    applyAssetBundle(bundle);
    if (bundle.defaultLayout) this.setLayout(bundle.defaultLayout);
  }

  setLayout(layout: Parameters<OfficeState['setLayout']>[0]): void {
    this.officeState.setLayout(layout);
  }

  dispatch(command: PixelOfficeCommand): void {
    switch (command.type) {
      case 'loadAssets':
        this.loadAssets(command.bundle);
        break;
      case 'setLayout':
        this.setLayout(command.layout);
        break;
      case 'setAgents':
        this.officeState.setAgents(command.agents);
        break;
      case 'upsertAgent':
        this.officeState.upsertAgent(command.agent);
        break;
      case 'removeAgent':
        this.officeState.removeAgent(command.id);
        break;
      case 'moveAgentTo':
        this.officeState.moveAgentTo(command.id, command.col, command.row);
        break;
      case 'stopAgent':
        this.officeState.stopAgent(command.id);
        break;
      case 'sendAgentToSeat':
        this.officeState.sendAgentToSeat(command.id);
        break;
      case 'seatAgentNow':
        this.officeState.seatAgentNow(command.id);
        break;
      case 'wanderAgent':
        this.officeState.wanderAgent(command.id);
        break;
      case 'setAgentMode':
        this.officeState.setAgentMode(command.id, command.mode, command.tool);
        break;
      case 'setAgentActive':
        this.officeState.setAgentActive(command.id, command.isActive, command.tool);
        break;
      case 'setAgentTool':
        this.officeState.setAgentTool(command.id, command.tool);
        break;
      case 'setAgentStatus':
        this.officeState.setAgentStatus(command.id, command.text, command.detail, command.ttlSeconds);
        break;
      case 'focusAgent':
        this.officeState.cameraFollowId = command.id;
        break;
      case 'panTo':
        this.pan = { x: command.x, y: command.y };
        break;
      case 'showBubble':
        this.officeState.showBubble(command.id, command.bubbleType);
        break;
      case 'clearBubble':
        this.officeState.clearBubble(command.id);
        break;
    }
  }

  dispatchJson(commandJson: string): void {
    this.dispatch(JSON.parse(commandJson) as PixelOfficeCommand);
  }

  on<K extends keyof PixelOfficeEventMap>(eventName: K, listener: Listener<K>): () => void {
    const list = this.getListenerBucket(eventName);
    list.push(listener as (payload: unknown) => void);
    return () => {
      const index = list.indexOf(listener as (payload: unknown) => void);
      if (index >= 0) list.splice(index, 1);
    };
  }

  destroy(): void {
    this.stopLoop?.();
    this.resizeObserver?.disconnect();
    this.canvas.remove();
  }

  private resizeCanvas(): void {
    const rect = this.container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(rect.width * dpr);
    this.canvas.height = Math.round(rect.height * dpr);
  }

  private bindCanvasEvents(): void {
    this.canvas.addEventListener('click', (event) => {
      const world = this.screenToWorld(event.clientX, event.clientY);
      if (!world) return;
      const hitId = this.hitTestAgent(world.worldX, world.worldY);
      if (hitId !== null) this.emit('agentClick', { id: hitId });
    });
  }

  private emit<K extends keyof PixelOfficeEventMap>(eventName: K, payload: PixelOfficeEventMap[K]): void {
    const listeners = this.getListenerBucket(eventName);
    listeners.forEach((listener) => listener(payload));
  }

  private getListenerBucket<K extends keyof PixelOfficeEventMap>(eventName: K): Array<(payload: unknown) => void> {
    const existing = this.listeners[eventName];
    if (existing) return existing;
    const created: Array<(payload: unknown) => void> = [];
    this.listeners[eventName] = created;
    return created;
  }

  private screenToWorld(clientX: number, clientY: number): { worldX: number; worldY: number } | null {
    const rect = this.canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const dpr = window.devicePixelRatio || 1;
    const deviceX = (clientX - rect.left) * dpr;
    const deviceY = (clientY - rect.top) * dpr;
    return {
      worldX: (deviceX - this.offset.x) / this.zoom,
      worldY: (deviceY - this.offset.y) / this.zoom,
    };
  }

  private hitTestAgent(worldX: number, worldY: number): number | null {
    for (const ch of this.officeState.getCharacters().slice().reverse()) {
      const left = ch.x - 8;
      const right = ch.x + 8;
      const top = ch.y - 24;
      const bottom = ch.y + 8;
      if (worldX >= left && worldX <= right && worldY >= top && worldY <= bottom) return ch.id;
    }
    return null;
  }

  private updateCameraFollow(): void {
    const followId = this.officeState.cameraFollowId;
    if (followId === null) return;
    const ch = this.officeState.characters.get(followId);
    if (!ch) return;
    const layout = this.officeState.getLayout();
    const mapWidth = layout.cols * TILE_SIZE * this.zoom;
    const mapHeight = layout.rows * TILE_SIZE * this.zoom;
    const targetX = mapWidth / 2 - ch.x * this.zoom;
    const targetY = mapHeight / 2 - ch.y * this.zoom;
    const dx = targetX - this.pan.x;
    const dy = targetY - this.pan.y;
    if (Math.abs(dx) < CAMERA_FOLLOW_SNAP_THRESHOLD && Math.abs(dy) < CAMERA_FOLLOW_SNAP_THRESHOLD) {
      this.pan = { x: targetX, y: targetY };
      return;
    }
    this.pan = { x: this.pan.x + dx * CAMERA_FOLLOW_LERP, y: this.pan.y + dy * CAMERA_FOLLOW_LERP };
  }
}
