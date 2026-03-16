"""SOFEM MES v2.0 — Auth Routes"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import create_token, require_admin, get_current_user, hash_pin, verify_pin
from models import PINLogin, UserCreate, UserUpdate

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(data: PINLogin, db=Depends(get_db)):
    user = q(db, "SELECT * FROM users WHERE actif=TRUE", one=False)
    # find user by PIN
    matched = None
    for u in user:
        if verify_pin(data.pin, u["pin_hash"]):
            matched = u
            break
    if not matched:
        raise HTTPException(401, "PIN incorrect")
    token = create_token(
        user_id=matched["id"],
        role=matched["role"],
        nom=matched["nom"],
        prenom=matched["prenom"],
        operateur_id=matched.get("operateur_id")
    )
    return {
        "token": token,
        "role": matched["role"],
        "nom": matched["nom"],
        "prenom": matched["prenom"],
        "operateur_id": matched.get("operateur_id")
    }

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user

@router.get("/users", dependencies=[Depends(require_admin)])
def list_users(db=Depends(get_db)):
    return serialize(q(db, "SELECT id,nom,prenom,role,operateur_id,actif,created_at FROM users ORDER BY role,nom"))

@router.post("/users", dependencies=[Depends(require_admin)], status_code=201)
def create_user(data: UserCreate, db=Depends(get_db)):
    uid = exe(db, """
        INSERT INTO users (nom,prenom,role,pin_hash,operateur_id,actif)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (data.nom, data.prenom, data.role, hash_pin(data.pin), data.operateur_id, data.actif))
    return {"id": uid, "message": "Utilisateur créé"}

@router.put("/users/{uid}", dependencies=[Depends(require_admin)])
def update_user(uid: int, data: UserUpdate, db=Depends(get_db)):
    fields, params = [], []
    if data.nom    is not None: fields.append("nom=%s");    params.append(data.nom)
    if data.prenom is not None: fields.append("prenom=%s"); params.append(data.prenom)
    if data.role   is not None: fields.append("role=%s");   params.append(data.role)
    if data.pin    is not None: fields.append("pin_hash=%s"); params.append(hash_pin(data.pin))
    if data.actif  is not None: fields.append("actif=%s");  params.append(data.actif)
    if fields:
        params.append(uid)
        exe(db, f"UPDATE users SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "Utilisateur mis à jour"}

@router.delete("/users/{uid}", dependencies=[Depends(require_admin)])
def delete_user(uid: int, db=Depends(get_db)):
    exe(db, "UPDATE users SET actif=FALSE WHERE id=%s", (uid,))
    return {"message": "Utilisateur désactivé"}
