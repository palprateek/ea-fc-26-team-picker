export async function startCamera(videoEl) {
  // No width/height constraints — let the camera pick its native mode.
  // overlay.js handles arbitrary aspect ratios via the object-fit: cover
  // math in drawVideoFrame, and getFaceAnchor maps detection coordinates
  // back into the cropped canvas. This is the same approach Google Meet
  // and Zoom use to avoid the zoomed/cropped artifacts you get when you
  // force a specific resolution the camera doesn't natively support.
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'user' },
    audio: false,
  });

  videoEl.srcObject = stream;
  await new Promise(resolve => {
    videoEl.onloadedmetadata = resolve;
  });
  await videoEl.play();

  return {
    width: videoEl.videoWidth,
    height: videoEl.videoHeight,
    stop() {
      stream.getTracks().forEach(t => t.stop());
    },
  };
}
