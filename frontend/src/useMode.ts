import { api } from "@/src/api";
import { useAuth } from "@/src/auth";

/** Switch the app between Passenger and Driver mode (saved on the account). */
export function useSetMode() {
  const { setUser } = useAuth();
  return async (mode: "passenger" | "driver") => setUser(await api("/me", { method: "PUT", body: { account_type: mode } }));
}
