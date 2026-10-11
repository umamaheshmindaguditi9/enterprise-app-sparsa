// Legacy read-only lists have no item IDs. Content + duplicate occurrence stays
// stable when different entries move, without changing persisted medical records.
export const stableEntries = (items = []) => {
  const occurrences = new Map();
  return items.map(value => {
    const identity = value?.id || JSON.stringify(value);
    const occurrence = occurrences.get(identity) || 0;
    occurrences.set(identity, occurrence + 1);
    return { key: `${identity}:${occurrence}`, value };
  });
};