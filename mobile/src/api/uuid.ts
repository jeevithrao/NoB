export function uuidv4(): string {
  // Not cryptographically strong, which is fine here — these ids are only
  // used as client-generated correlation ids (device id, event dedupe key),
  // never as security tokens.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
