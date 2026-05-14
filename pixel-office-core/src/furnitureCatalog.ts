import type { FurnitureCatalogEntry, LoadedAssetData } from './types.js';

let internalCatalog: FurnitureCatalogEntry[] = [];
const stateGroups = new Map<string, string>();
const offToOn = new Map<string, string>();
const animationGroups = new Map<string, string[]>();

export function buildDynamicCatalog(assets: LoadedAssetData): boolean {
  if (!assets.catalog.length) return false;
  stateGroups.clear();
  offToOn.clear();
  animationGroups.clear();
  const entries = assets.catalog
    .map((asset): FurnitureCatalogEntry | null => {
      const sprite = assets.sprites[asset.id];
      if (!sprite) return null;
      return {
        type: asset.id,
        label: asset.label,
        footprintW: asset.footprintW,
        footprintH: asset.footprintH,
        sprite,
        isDesk: asset.isDesk,
        category: asset.category,
        orientation: asset.orientation,
        canPlaceOnSurfaces: asset.canPlaceOnSurfaces,
        backgroundTiles: asset.backgroundTiles,
        canPlaceOnWalls: asset.canPlaceOnWalls,
        mirrorSide: asset.mirrorSide,
      } satisfies FurnitureCatalogEntry;
    })
    .filter((entry): entry is FurnitureCatalogEntry => entry !== null);
  internalCatalog = entries;

  const stateMap = new Map<string, Map<string, string>>();
  for (const asset of assets.catalog) {
    if (asset.groupId && asset.state) {
      const key = `${asset.groupId}|${asset.orientation || ''}`;
      let bucket = stateMap.get(key);
      if (!bucket) {
        bucket = new Map();
        stateMap.set(key, bucket);
      }
      if (asset.animationGroup && asset.frame !== undefined && asset.frame > 0) continue;
      bucket.set(asset.state, asset.id);
    }
  }
  for (const bucket of stateMap.values()) {
    const onId = bucket.get('on');
    const offId = bucket.get('off');
    if (onId && offId) {
      stateGroups.set(onId, offId);
      stateGroups.set(offId, onId);
      offToOn.set(offId, onId);
    }
  }

  const animCollector = new Map<string, Array<{ id: string; frame: number }>>();
  for (const asset of assets.catalog) {
    if (asset.animationGroup && asset.frame !== undefined) {
      let frames = animCollector.get(asset.animationGroup);
      if (!frames) {
        frames = [];
        animCollector.set(asset.animationGroup, frames);
      }
      frames.push({ id: asset.id, frame: asset.frame });
    }
  }
  for (const [groupId, frames] of animCollector) {
    frames.sort((a, b) => a.frame - b.frame);
    animationGroups.set(groupId, frames.map((frame) => frame.id));
  }

  for (const asset of assets.catalog) {
    if (asset.mirrorSide && asset.orientation === 'side') {
      const sideEntry = internalCatalog.find((entry) => entry.type === asset.id);
      if (sideEntry) {
        internalCatalog.push({ ...sideEntry, type: `${asset.id}:left`, orientation: 'left', mirrorSide: true });
      }
    }
  }
  return internalCatalog.length > 0;
}

export function getCatalogEntry(type: string): FurnitureCatalogEntry | undefined {
  return internalCatalog.find((entry) => entry.type === type);
}

export function getOnStateType(currentType: string): string {
  return offToOn.get(currentType) ?? currentType;
}

export function getAnimationFrames(type: string): string[] | null {
  for (const [, frames] of animationGroups) {
    if (frames.includes(type)) return frames;
  }
  return null;
}
