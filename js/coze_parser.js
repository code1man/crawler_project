function parseCozeEnvelope(result) {
  try {
    if (typeof result === 'string') result = JSON.parse(result);
  } catch (e) {
    return null;
  }
  let data = result && result.data !== undefined ? result.data : result;
  try {
    if (typeof data === 'string') data = JSON.parse(data);
  } catch (e) {
    // leave as-is
  }
  if (Array.isArray(data)) {
    return data.map(item => {
      if (typeof item === 'string') {
        try { return JSON.parse(item); } catch (e) { return item; }
      }
      return item;
    });
  }
  return data;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { parseCozeEnvelope };
} else {
  window.parseCozeEnvelope = parseCozeEnvelope;
}
