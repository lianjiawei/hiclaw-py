let internalCatalog = [];
const stateGroups = new Map();
const offToOn = new Map();
const animationGroups = new Map();
export function buildDynamicCatalog(assets) {
    if (!assets.catalog.length)
        return false;
    stateGroups.clear();
    offToOn.clear();
    animationGroups.clear();
    const entries = assets.catalog
        .map((asset) => {
        const sprite = assets.sprites[asset.id];
        if (!sprite)
            return null;
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
        };
    })
        .filter((entry) => entry !== null);
    internalCatalog = entries;
    const stateMap = new Map();
    for (const asset of assets.catalog) {
        if (asset.groupId && asset.state) {
            const key = `${asset.groupId}|${asset.orientation || ''}`;
            let bucket = stateMap.get(key);
            if (!bucket) {
                bucket = new Map();
                stateMap.set(key, bucket);
            }
            if (asset.animationGroup && asset.frame !== undefined && asset.frame > 0)
                continue;
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
    const animCollector = new Map();
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
export function getCatalogEntry(type) {
    return internalCatalog.find((entry) => entry.type === type);
}
export function getOnStateType(currentType) {
    return offToOn.get(currentType) ?? currentType;
}
export function getAnimationFrames(type) {
    for (const [, frames] of animationGroups) {
        if (frames.includes(type))
            return frames;
    }
    return null;
}
