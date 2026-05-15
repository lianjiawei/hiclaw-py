import type { Character, CharacterSprites, Seat, SpriteData, TileType as TileTypeVal } from './types.js';
export declare function createCharacter(id: number, palette: number, seatId: string | null, seat: Seat | null, hueShift?: number): Character;
export declare function updateCharacter(ch: Character, dt: number, walkableTiles: Array<{
    col: number;
    row: number;
}>, seats: Map<string, Seat>, tileMap: TileTypeVal[][], blockedTiles: Set<string>): void;
export declare function getCharacterSprite(ch: Character, sprites: CharacterSprites): SpriteData;
