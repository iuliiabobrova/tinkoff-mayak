import psycopg2

if __name__ == "__main__":
    with psycopg2.connect(host="db", port="5432", dbname="postgres", user="postgres", password="postgres") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tgbot_subscription;")
            print("total: " + str(cur.rowcount))
            cur.execute("SELECT * FROM tgbot_subscription WHERE strategy_id = 'sma_50_200';")
            print("sma_50_200: " + str(cur.rowcount))
            cur.execute("SELECT * FROM tgbot_subscription WHERE strategy_id = 'sma';")
            print("sma: " + str(cur.rowcount))
            cur.execute("UPDATE tgbot_subscription SET strategy_id = 'sma_50_200' WHERE strategy_id = 'sma';")
            print("update sma to sma_50_200: " + str(cur.rowcount))
            cur.execute("SELECT * FROM tgbot_subscription WHERE strategy_id = 'sma_50_200';")
            print("sma_50_200: " + str(cur.rowcount))