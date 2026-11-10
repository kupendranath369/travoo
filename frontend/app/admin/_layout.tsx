import { Stack, useRouter, useSegments } from "expo-router";
import React, { useEffect, useState } from "react";
import { View } from "react-native";

import { adminApi, loadAdminToken } from "@/src/adminApi";
import { Loading } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const OPEN = new Set(["login"]);

/** Server-verified guard for every admin page: no valid admin session -> /admin/login. */
export default function AdminLayout() {
  const { colors } = useTheme();
  const router = useRouter();
  const segments = useSegments();
  const sub = (segments[1] as string | undefined) ?? "index";
  const [ok, setOk] = useState(false);

  useEffect(() => {
    let alive = true;
    if (OPEN.has(sub)) {
      setOk(true);
      return;
    }
    setOk(false);
    (async () => {
      if (!(await loadAdminToken())) return router.replace("/admin/login");
      try {
        const me = await adminApi("/admin/auth/me");
        if (!alive) return;
        if (me.must_change_password && sub !== "change-password") return router.replace("/admin/change-password");
        if (sub === "index") return router.replace("/admin/dashboard");
        setOk(true);
      } catch {
        if (alive) router.replace("/admin/login");
      }
    })();
    return () => { alive = false; };
  }, [sub, router]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Stack screenOptions={{ headerShown: false }} />
      {!ok ? <View style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: colors.surface }}><Loading /></View> : null}
    </View>
  );
}
