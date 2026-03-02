/**
 * AdUnit Component - World Situation Monitor
 * Non-intrusive Google AdSense ad wrapper.
 * Renders only when AdSense is loaded and publisher ID is configured.
 */

import React, { useEffect, useRef } from 'react';

// Set your AdSense publisher ID here once approved
const ADSENSE_PUB_ID = 'ca-pub-XXXXXXXXXXXXXXXX';

// Don't render ads if publisher ID isn't configured yet
const isConfigured = ADSENSE_PUB_ID !== 'ca-pub-XXXXXXXXXXXXXXXX';

/**
 * Ad slot formats:
 * - 'banner'    : horizontal banner (side panel bottom, 320x100)
 * - 'rectangle' : medium rectangle (country profile, 300x250)
 * - 'leaderboard': thin banner (header area, 728x90)
 */
const AD_FORMATS = {
  banner: { width: '100%', height: '100px' },
  rectangle: { width: '100%', height: '250px' },
  leaderboard: { width: '100%', height: '90px' },
};

export default function AdUnit({ format = 'banner', slot = '', style = {} }) {
  const adRef = useRef(null);
  const pushed = useRef(false);

  useEffect(() => {
    if (!isConfigured || pushed.current) return;
    try {
      if (window.adsbygoogle && adRef.current) {
        window.adsbygoogle.push({});
        pushed.current = true;
      }
    } catch (e) {
      // AdSense not loaded — silently ignore
    }
  }, []);

  // Don't render anything if not configured
  if (!isConfigured) return null;

  const formatStyle = AD_FORMATS[format] || AD_FORMATS.banner;

  return (
    <div className="ad-unit-container" style={style}>
      <div className="ad-unit-label">Sponsored</div>
      <ins
        ref={adRef}
        className="adsbygoogle"
        style={{
          display: 'block',
          ...formatStyle,
          overflow: 'hidden',
        }}
        data-ad-client={ADSENSE_PUB_ID}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </div>
  );
}
