export declare const TileType: {
    readonly WALL: 0;
    readonly FLOOR_1: 1;
    readonly FLOOR_2: 2;
    readonly FLOOR_3: 3;
    readonly FLOOR_4: 4;
    readonly FLOOR_5: 5;
    readonly FLOOR_6: 6;
    readonly FLOOR_7: 7;
    readonly FLOOR_8: 8;
    readonly FLOOR_9: 9;
    readonly VOID: 255;
};
export type TileType = (typeof TileType)[keyof typeof TileType];
export declare const CharacterState: {
    readonly IDLE: "idle";
    readonly WALK: "walk";
    readonly TYPE: "type";
};
export type CharacterState = (typeof CharacterState)[keyof typeof CharacterState];
export declare const Direction: {
    readonly DOWN: 0;
    readonly LEFT: 1;
    readonly RIGHT: 2;
    readonly UP: 3;
};
export type Direction = (typeof Direction)[keyof typeof Direction];
export type SpriteData = string[][];
export interface ColorValue {
    h: number;
    s: number;
    b: number;
    c: number;
    colorize?: boolean;
}
export interface Seat {
    uid: string;
    seatCol: number;
    seatRow: number;
    facingDir: Direction;
    assigned: boolean;
}
export interface FurnitureCatalogAsset {
    id: string;
    name: string;
    label: string;
    category: string;
    file: string;
    width: number;
    height: number;
    footprintW: number;
    footprintH: number;
    isDesk: boolean;
    canPlaceOnWalls: boolean;
    canPlaceOnSurfaces?: boolean;
    backgroundTiles?: number;
    groupId?: string;
    orientation?: string;
    state?: string;
    mirrorSide?: boolean;
    rotationScheme?: string;
    animationGroup?: string;
    frame?: number;
}
export interface FurnitureCatalogEntry {
    type: string;
    label: string;
    footprintW: number;
    footprintH: number;
    sprite: SpriteData;
    isDesk: boolean;
    category?: string;
    orientation?: string;
    canPlaceOnSurfaces?: boolean;
    backgroundTiles?: number;
    canPlaceOnWalls?: boolean;
    mirrorSide?: boolean;
}
export interface LoadedAssetData {
    catalog: FurnitureCatalogAsset[];
    sprites: Record<string, SpriteData>;
}
export interface PlacedFurniture {
    uid: string;
    type: string;
    col: number;
    row: number;
    color?: ColorValue;
}
export interface FurnitureInstance {
    sprite: SpriteData;
    x: number;
    y: number;
    zY: number;
    mirrored?: boolean;
}
export interface OfficeLayout {
    version: 1;
    cols: number;
    rows: number;
    tiles: TileType[];
    furniture: PlacedFurniture[];
    tileColors?: Array<ColorValue | null>;
    layoutRevision?: number;
}
export interface CharacterDirectionSprites {
    down: SpriteData[];
    up: SpriteData[];
    right: SpriteData[];
}
export interface CharacterSprites {
    walk: Record<Direction, [SpriteData, SpriteData, SpriteData, SpriteData]>;
    typing: Record<Direction, [SpriteData, SpriteData]>;
    reading: Record<Direction, [SpriteData, SpriteData]>;
}
export type BubbleType = 'permission' | 'waiting' | null;
export type AgentMode = 'working' | 'thinking' | 'waiting' | 'blocked' | 'idle';
export interface Character {
    id: number;
    state: CharacterState;
    dir: Direction;
    x: number;
    y: number;
    tileCol: number;
    tileRow: number;
    path: Array<{
        col: number;
        row: number;
    }>;
    moveProgress: number;
    currentTool: string | null;
    palette: number;
    hueShift: number;
    frame: number;
    frameTimer: number;
    wanderTimer: number;
    wanderCount: number;
    wanderLimit: number;
    isActive: boolean;
    seatId: string | null;
    seatTimer: number;
    label?: string;
    statusText?: string;
    statusDetail?: string;
    statusTimer: number;
    bubbleType: BubbleType;
    bubbleTimer: number;
}
export interface PixelOfficeAssetBundle {
    characters: CharacterDirectionSprites[];
    floors: SpriteData[];
    walls: SpriteData[][];
    furniture: LoadedAssetData;
    defaultLayout?: OfficeLayout;
}
export interface PixelOfficeAgentInput {
    id: number;
    palette?: number;
    hueShift?: number;
    seatId?: string | null;
    label?: string;
    currentTool?: string | null;
    isActive?: boolean;
}
export interface PixelOfficeCommandMap {
    loadAssets: {
        bundle: PixelOfficeAssetBundle;
    };
    setLayout: {
        layout: OfficeLayout;
    };
    setAgents: {
        agents: PixelOfficeAgentInput[];
    };
    upsertAgent: {
        agent: PixelOfficeAgentInput;
    };
    removeAgent: {
        id: number;
    };
    moveAgentTo: {
        id: number;
        col: number;
        row: number;
    };
    stopAgent: {
        id: number;
    };
    sendAgentToSeat: {
        id: number;
    };
    seatAgentNow: {
        id: number;
    };
    wanderAgent: {
        id: number;
    };
    setAgentMode: {
        id: number;
        mode: AgentMode;
        tool?: string | null;
    };
    setAgentActive: {
        id: number;
        isActive: boolean;
        tool?: string | null;
    };
    setAgentTool: {
        id: number;
        tool: string | null;
    };
    setAgentStatus: {
        id: number;
        text: string;
        detail?: string | null;
        ttlSeconds?: number | null;
    };
    focusAgent: {
        id: number | null;
    };
    panTo: {
        x: number;
        y: number;
    };
    showBubble: {
        id: number;
        bubbleType: 'permission' | 'waiting';
    };
    clearBubble: {
        id: number;
    };
}
export type PixelOfficeCommand = {
    [K in keyof PixelOfficeCommandMap]: {
        type: K;
    } & PixelOfficeCommandMap[K];
}[keyof PixelOfficeCommandMap];
export interface PixelOfficeEventMap {
    agentClick: {
        id: number;
    };
}
