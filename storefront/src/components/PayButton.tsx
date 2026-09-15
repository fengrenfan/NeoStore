"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, payOrder } from "@/lib/api";

/**
 * Confirms the mock payment and refreshes the order.
 *
 * It hits `POST /store/orders/{number}/pay`, which stands in for the gateway's
 * callback. The backend answers 404 when `ENABLE_MOCK_PAYMENTS` is off, so the
 * error surfacing here is informational rather than alarming.
 */
export function PayButton({
  number,
  labels,
}: {
  number: string;
  labels: { pay: string; paying: string; failed: string };
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function pay() {
    setBusy(true);
    setMessage(null);
    try {
      await payOrder(number);
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof ApiError ? `${labels.failed} (${error.code})` : labels.failed,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <button className="btn-primary" disabled={busy} onClick={pay} type="button">
        {busy ? labels.paying : labels.pay}
      </button>
      {message ? <p className="text-xs text-red-400">{message}</p> : null}
    </div>
  );
}
