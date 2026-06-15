export async function startCamera(videoEl) {
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: 'user',
      width:  { ideal: isMobile ? 480  : 720  },
      height: { ideal: isMobile ? 640  : 1280 },
    },
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
