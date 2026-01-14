from fastapi import Body, FastAPI

app = FastAPI()

@app.get("/")
def read_all_movies():
    return "hello world"
