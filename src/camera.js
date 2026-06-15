export async function startCamera(videoEl) {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'user', width: { ideal: 720 }, height: { ideal: 1280 } },
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
