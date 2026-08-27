import { AcceptanceCheckSettings } from "@/components/acceptance-check-settings";
import { RateLimitSettings } from "@/components/rate-limit-settings";

export function SettingsPanel() {
  return (
    <div className="mt-5 space-y-5">
      <AcceptanceCheckSettings />
      <RateLimitSettings />
    </div>
  );
}
