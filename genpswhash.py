from security import DeviceSecurity

def main():
    # --- Password di test ---
    password = "test"

    # --- Genera hash bcrypt ---
    password_hash = DeviceSecurity.hash_password(password)
    print("Password originale:", password)
    print("Hash da salvare nel DB:", password_hash)

    # --- Verifica corretta ---
    login_ok = DeviceSecurity.verify_password(password, password_hash)
    print("Verifica corretta:", login_ok)

    # --- Verifica con password sbagliata ---
    login_fail = DeviceSecurity.verify_password("PasswordSbagliata123", password_hash)
    print("Verifica password sbagliata:", login_fail)


if __name__ == "__main__":
    main()
