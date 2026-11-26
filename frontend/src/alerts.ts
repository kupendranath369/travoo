import { createAudioPlayer, setAudioModeAsync } from "expo-audio";
import * as Haptics from "expo-haptics";
import { useEffect, useRef } from "react";
import { Platform } from "react-native";

import alertSound from "../assets/sounds/alert.wav";

const REQUEST_TYPES = new Set(["booking_request", "new_booking", "hire_request", "local_hire_request"]);

let player: any = null;

/** Loud two-tone ringtone + strong vibration for incoming booking requests. */
export function playBookingAlert() {
  try {
    if (Platform.OS === "web") {
      if (typeof navigator !== "undefined" && "vibrate" in navigator) navigator.vibrate([300, 100, 300, 100, 600]);
      return;
    }
    setAudioModeAsync({ playsInSilentMode: true }).catch(() => {});
    if (!player) player = createAudioPlayer(alertSound);
    player.seekTo(0);
    player.play();
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
  } catch {}
}

/** Poll notifications and ring loudly when a new booking request arrives. */
export function useBookingAlertSound(apiGet: (path: string) => Promise<any>, enabled = true) {
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let stop = false;
    const tick = async () => {
      try {
        const r = await apiGet("/notifications");
        const items: any[] = r?.items ?? [];
        const reqs = items.filter((n) => REQUEST_TYPES.has(n.type));
        if (seen.current === null) {
          seen.current = new Set(reqs.map((n) => n.notif_id)); // baseline: don't ring for old ones
          return;
        }
        const fresh = reqs.filter((n) => !seen.current!.has(n.notif_id));
        if (fresh.length) {
          seen.current = new Set(reqs.map((n) => n.notif_id));
          playBookingAlert();
        }
      } catch {}
      if (!stop) setTimeout(tick, 12000);
    };
    tick();
    return () => { stop = true; };
  }, [enabled, apiGet]);
}
