import { useCallback, useState } from 'react';

/**
 * Panodaki metni okur. Tarayıcı izin vermezse sessizce false döner,
 * kullanıcı elle yapıştırmaya devam edebilir.
 */
export function useClipboardPaste(onText: (text: string) => void) {
  const [denied, setDenied] = useState(false);

  const paste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text.trim()) {
        onText(text.trim());
        setDenied(false);
        return true;
      }
    } catch {
      setDenied(true);
    }
    return false;
  }, [onText]);

  return { paste, denied };
}
