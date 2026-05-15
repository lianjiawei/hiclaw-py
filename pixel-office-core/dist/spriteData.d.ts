import type { CharacterDirectionSprites, CharacterSprites } from './types.js';
export declare function setCharacterTemplates(data: CharacterDirectionSprites[]): void;
export declare function getLoadedCharacterCount(): number;
export declare function getCharacterSprites(paletteIndex: number, hueShift?: number): CharacterSprites;
export declare function decodeCharacterImage(image: HTMLImageElement): CharacterDirectionSprites;
