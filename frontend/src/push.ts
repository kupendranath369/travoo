import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Notifications from "expo-notifications";
import * as Linking from "expo-linking";
import { useRouter } from "expo-router";
import { useEffect } from "react";
import { Alert, Platform } from "react-native";

import { api } from "@/src/api";

async function registerForPush() {
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== "granted") return;
  const tokenResp = await Notifications.getDevicePushTokenAsync();
  await api("/register-push", { body: { platform: Platform.OS, device_token: String(tokenResp.data) } });
}

const openUrl = (router: ReturnType<typeof useRouter>, data: any) => {
  const url = data?.deeplink || data?.action_url;
  if (!url) return;
  if (String(url).startsWith("http")) Linking.openURL(url);
  else router.push(url);
};

/** Registers this phone for push (every app open) and opens the right screen when a push is tapped. Native only. */
export function usePushNotifications(userId?: string) {
  const router = useRouter();
  useEffect(() => {
    if (Platform.OS === "web" || !userId) return;
    registerForPush().catch(() => {});
    const tapSub = Notifications.addNotificationResponseReceivedListener((r) => openUrl(router, r.notification.request.content.data));
    Notifications.getLastNotificationResponseAsync().then((r) => { if (r) openUrl(router, r.notification.request.content.data); });
    (async () => {
      const { status, canAskAgain } = await Notifications.getPermissionsAsync();
      if (status !== "denied" || canAskAgain) return;
      const last = await AsyncStorage.getItem("pushNudgeAt");
      if (last && Date.now() - Number(last) <= 7 * 24 * 60 * 60 * 1000) return;
      const stamp = () => AsyncStorage.setItem("pushNudgeAt", String(Date.now()));
      Alert.alert("Turn on notifications", "Allow notifications so you never miss a booking request or ride update.", [
        { text: "Later", style: "cancel", onPress: stamp },
        { text: "Open Settings", onPress: () => { stamp(); Linking.openSettings(); } },
      ]);
    })();
    return () => tapSub.remove();
  }, [userId, router]);
}
