"""
Modèle LOGIQUE (SQLAlchemy) dérivé du modèle conceptuel M5.

Les associations 1-à-plusieurs du MCD deviennent des clés étrangères.
Ces tables constituent la couche de "service" (PostgreSQL) alimentée après
nettoyage depuis la zone Curated du datalake.
"""
from __future__ import annotations

from sqlalchemy import (Column, Date, DateTime, Float, ForeignKey, Integer,
                        String, func)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Utilisateur(Base):
    __tablename__ = "utilisateur"
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)          # SENSIBLE (M5)
    ville = Column(String)                           # SENSIBLE (M5)
    date_inscription = Column(Date)
    plantes = relationship("Plante", back_populates="utilisateur")


class Espece(Base):
    __tablename__ = "espece"
    id = Column(Integer, primary_key=True)
    nom_sci = Column(String, nullable=False)
    lumiere = Column(Float)
    humidite = Column(Float)
    temp_min = Column(Float)
    temp_max = Column(Float)
    seuil_sol_sec = Column(Float, default=30.0)


class Plante(Base):
    __tablename__ = "plante"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("utilisateur.id"))
    espece_id = Column(Integer, ForeignKey("espece.id"))
    emplacement = Column(String)
    taille_pot = Column(Integer)
    date_ajout = Column(Date)
    utilisateur = relationship("Utilisateur", back_populates="plantes")


class HistoriqueSoin(Base):
    __tablename__ = "historique_soin"
    id = Column(Integer, primary_key=True)
    plante_id = Column(Integer, ForeignKey("plante.id"))
    type_action = Column(String)
    date = Column(Date)
    quantite = Column(Float)
    photo_ref = Column(String)


class MesureCapteur(Base):
    __tablename__ = "mesure_capteur"
    id = Column(Integer, primary_key=True)
    plante_id = Column(Integer, ForeignKey("plante.id"))
    humidite = Column(Float)
    sol = Column(Float)
    temperature = Column(Float)
    lux = Column(Float)
    horodatage = Column(DateTime, server_default=func.now())


class ObsMeteo(Base):
    __tablename__ = "obs_meteo"
    id = Column(Integer, primary_key=True)
    ville = Column(String)
    temp = Column(Float)
    pluie = Column(Float)
    vent = Column(Float)
    horodatage = Column(DateTime, server_default=func.now())


class Recommandation(Base):
    __tablename__ = "recommandation"
    id = Column(Integer, primary_key=True)
    plante_id = Column(Integer, ForeignKey("plante.id"))
    type = Column(String)          # "A" (conseil) ou "C" (verdict)
    verdict = Column(String)
    texte = Column(String)
    confiance = Column(Float)
    date = Column(DateTime, server_default=func.now())


class AnalyseImage(Base):
    __tablename__ = "analyse_image"
    id = Column(Integer, primary_key=True)
    plante_id = Column(Integer, ForeignKey("plante.id"))
    espece_predite = Column(String)
    score = Column(Float)
    date = Column(DateTime, server_default=func.now())
