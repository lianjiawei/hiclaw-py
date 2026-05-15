import type { FurnitureCatalogEntry, LoadedAssetData } from './types.js';
export declare function buildDynamicCatalog(assets: LoadedAssetData): boolean;
export declare function getCatalogEntry(type: string): FurnitureCatalogEntry | undefined;
export declare function getOnStateType(currentType: string): string;
export declare function getAnimationFrames(type: string): string[] | null;
