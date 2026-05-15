import { CAMERA_FOLLOW_LERP, CAMERA_FOLLOW_SNAP_THRESHOLD, TILE_SIZE } from './constants.js';
import { applyAssetBundle } from './browserAssetLoader.js';
import { startGameLoop } from './gameLoop.js';
import { OfficeState } from './officeState.js';
import { renderFrame } from './renderer.js';
export class PixelOfficeController {
    canvas;
    officeState;
    container;
    stopLoop = null;
    resizeObserver = null;
    listeners = {};
    offset = { x: 0, y: 0 };
    pan = { x: 0, y: 0 };
    zoom;
    constructor(container, options = {}) {
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
                if (this.officeState.cameraFollowId !== null)
                    this.updateCameraFollow();
                const result = renderFrame(ctx, this.canvas.width, this.canvas.height, this.officeState.tileMap, this.officeState.furniture, this.officeState.getCharacters(), this.zoom, this.pan.x, this.pan.y, this.officeState.getLayout().tileColors, this.officeState.getLayout().cols, this.officeState.getLayout().rows);
                this.offset = { x: result.offsetX, y: result.offsetY };
            },
        });
    }
    loadAssets(bundle) {
        applyAssetBundle(bundle);
        if (bundle.defaultLayout)
            this.setLayout(bundle.defaultLayout);
    }
    setLayout(layout) {
        this.officeState.setLayout(layout);
    }
    dispatch(command) {
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
    dispatchJson(commandJson) {
        this.dispatch(JSON.parse(commandJson));
    }
    on(eventName, listener) {
        const list = this.getListenerBucket(eventName);
        list.push(listener);
        return () => {
            const index = list.indexOf(listener);
            if (index >= 0)
                list.splice(index, 1);
        };
    }
    destroy() {
        this.stopLoop?.();
        this.resizeObserver?.disconnect();
        this.canvas.remove();
    }
    resizeCanvas() {
        const rect = this.container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = Math.round(rect.width * dpr);
        this.canvas.height = Math.round(rect.height * dpr);
    }
    bindCanvasEvents() {
        this.canvas.addEventListener('click', (event) => {
            const world = this.screenToWorld(event.clientX, event.clientY);
            if (!world)
                return;
            const hitId = this.hitTestAgent(world.worldX, world.worldY);
            if (hitId !== null)
                this.emit('agentClick', { id: hitId });
        });
    }
    emit(eventName, payload) {
        const listeners = this.getListenerBucket(eventName);
        listeners.forEach((listener) => listener(payload));
    }
    getListenerBucket(eventName) {
        const existing = this.listeners[eventName];
        if (existing)
            return existing;
        const created = [];
        this.listeners[eventName] = created;
        return created;
    }
    screenToWorld(clientX, clientY) {
        const rect = this.canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0)
            return null;
        const dpr = window.devicePixelRatio || 1;
        const deviceX = (clientX - rect.left) * dpr;
        const deviceY = (clientY - rect.top) * dpr;
        return {
            worldX: (deviceX - this.offset.x) / this.zoom,
            worldY: (deviceY - this.offset.y) / this.zoom,
        };
    }
    hitTestAgent(worldX, worldY) {
        for (const ch of this.officeState.getCharacters().slice().reverse()) {
            const left = ch.x - 8;
            const right = ch.x + 8;
            const top = ch.y - 24;
            const bottom = ch.y + 8;
            if (worldX >= left && worldX <= right && worldY >= top && worldY <= bottom)
                return ch.id;
        }
        return null;
    }
    updateCameraFollow() {
        const followId = this.officeState.cameraFollowId;
        if (followId === null)
            return;
        const ch = this.officeState.characters.get(followId);
        if (!ch)
            return;
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
