export interface User {
  id: string;
  phone: string;
  name: string | null;
  email: string | null;
  is_verified: boolean;
  is_onboarded: boolean;
  role: string;
  created_at: string;
}
