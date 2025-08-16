from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://chatbot:Tho%40123SS@69.197.187.234:5432/chatbot_db?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()
    print("Done setup")