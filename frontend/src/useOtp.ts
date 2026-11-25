import { useEffect, useState } from "react";

import { api } from "@/src/api";

let cached: boolean | null = null;

/** Mobile OTP is switched on only after the MSG91 key is configured on the server. */
export function useOtpEnabled() {
  const [on, setOn] = useState<boolean | null>(cached);
  useEffect(() => {
    if (cached !== null) return;
    api("/auth/otp/status").then((r) => { cached = !!r.enabled; setOn(cached); }).catch(() => setOn(false));
  }, []);
  return on;
}
