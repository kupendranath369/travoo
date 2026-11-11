import React from "react";

import { DriverVerificationForm } from "@/src/components/DriverVerificationForm";

// AI document reading was removed: verification is manual only. Old links land on the same manual form.
export default function AIVerificationScreen() {
  return <DriverVerificationForm />;
}
