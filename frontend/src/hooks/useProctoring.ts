import { useState, useEffect, useRef } from "react";

export interface UseProctoringResult {
  isFullscreen: boolean;
  visibilityViolations: number;
  webcamStream: MediaStream | null;
  requestFullscreen: () => void;
  startWebcam: () => Promise<void>;
  stopWebcam: () => void;
  resetViolations: () => void;
  error: string | null;
}

export function useProctoring(onViolation?: (type: "tab_switch" | "fullscreen_exit", count: number) => void): UseProctoringResult {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [visibilityViolations, setVisibilityViolations] = useState(0);
  const [webcamStream, setWebcamStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isFullscreenRef = useRef(false);

  // 1. Monitor Tab Switches (Visibility API)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        setVisibilityViolations((prev) => {
          const next = prev + 1;
          if (onViolation) onViolation("tab_switch", next);
          return next;
        });
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [onViolation]);

  // 2. Monitor Fullscreen Exit
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isCurrentlyFullscreen = !!document.fullscreenElement;
      setIsFullscreen(isCurrentlyFullscreen);

      // If we exit fullscreen after starting the test, trigger violation
      if (!isCurrentlyFullscreen && isFullscreenRef.current) {
        setVisibilityViolations((prev) => {
          const next = prev + 1;
          if (onViolation) onViolation("fullscreen_exit", next);
          return next;
        });
      }
      
      isFullscreenRef.current = isCurrentlyFullscreen;
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [onViolation]);

  // 3. Request Fullscreen
  const requestFullscreen = () => {
    const element = document.documentElement;
    if (element.requestFullscreen) {
      element.requestFullscreen().catch((err) => {
        setError("Failed to enable fullscreen mode: " + err.message);
      });
    }
  };

  // 4. Start Webcam Feed (Webcam Monitoring)
  const startWebcam = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { width: 320, height: 240, frameRate: 15 } 
      });
      setWebcamStream(stream);
    } catch (err: any) {
      setError("Failed to access webcam: " + (err.message || "Unknown error"));
      console.error(err);
    }
  };

  // 5. Stop Webcam Feed
  const stopWebcam = () => {
    if (webcamStream) {
      webcamStream.getTracks().forEach((track) => track.stop());
      setWebcamStream(null);
    }
  };

  const resetViolations = () => {
    setVisibilityViolations(0);
  };

  // Clean up webcam stream on unmount
  useEffect(() => {
    return () => {
      if (webcamStream) {
        webcamStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [webcamStream]);

  return {
    isFullscreen,
    visibilityViolations,
    webcamStream,
    requestFullscreen,
    startWebcam,
    stopWebcam,
    resetViolations,
    error,
  };
}
