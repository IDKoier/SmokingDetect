import bcrypt

plain_password = "410906235"

# 生成一個鹽，這裡假設你手動設置為這個鹽
salt = bcrypt.gensalt(rounds=12)  # rounds=12 表示加密的計算複雜度
# 使用明文密碼和鹽進行加密
#hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), b'$2b$12$J0tCLP3.YFyj.qnUFP6yy.')
# 顯示加密後的密文
print(salt)
print("Encrypted password:", hashed_password.decode('utf-8'))
#$2b$12$J0tCLP3.YFyj.qnUFP6yy.zGyt4JJ0gYGKpmagd7RCWswc6KIymtu