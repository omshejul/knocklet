const allowedProtocols = new Set(["http:", "https:"]);

function createExternalLinkHandler({ shell, onError }) {
  return ({ url }) => {
    let parsedUrl;
    try {
      parsedUrl = new URL(url);
      if (!allowedProtocols.has(parsedUrl.protocol)) {
        throw new Error(`Unsupported link protocol: ${parsedUrl.protocol}`);
      }
    } catch (error) {
      onError(error);
      return { action: "deny" };
    }

    shell.openExternal(parsedUrl.href).catch(onError);
    return { action: "deny" };
  };
}

module.exports = { createExternalLinkHandler };
