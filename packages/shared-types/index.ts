export type UserStatus = "ACTIVE" | "SUSPENDED" | "DELETED";

export interface UserDto {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  avatar_url: string | null;
  status: UserStatus;
  is_super_admin: boolean;
}
