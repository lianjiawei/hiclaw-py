export interface GameLoopCallbacks {
    update: (dt: number) => void;
    render: (ctx: CanvasRenderingContext2D) => void;
}
export declare function startGameLoop(canvas: HTMLCanvasElement, callbacks: GameLoopCallbacks): () => void;
