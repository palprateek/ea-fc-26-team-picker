import { FaceDetector, FilesetResolver } from '@mediapipe/tasks-vision';

const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite';

export async function createFaceDetector() {
  const vision = await FilesetResolver.forVisionTasks(
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
  );

  const detector = await FaceDetector.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: MODEL_URL,
      delegate: 'GPU',
    },
    runningMode: 'VIDEO',
    minDetectionConfidence: 0.5,
  });

  let lastTimestamp = -1;

  return {
    detect(videoEl, timestamp) {
      if (timestamp <= lastTimestamp) return [];
      lastTimestamp = timestamp;

      const results = detector.detectForVideo(videoEl, timestamp);
      return results.detections.map(d => ({
        x: d.boundingBox.originX,
        y: d.boundingBox.originY,
        width: d.boundingBox.width,
        height: d.boundingBox.height,
      }));
    },
  };
}
