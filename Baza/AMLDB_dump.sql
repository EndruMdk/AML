-- MySQL dump 10.13  Distrib 8.0.45, for macos15 (arm64)
--
-- Host: localhost    Database: AMLDB
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `Bet`
--

DROP TABLE IF EXISTS `Bet`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Bet` (
  `idB` int NOT NULL AUTO_INCREMENT,
  `idU` int NOT NULL,
  `idE` int NOT NULL,
  `amount` int NOT NULL,
  `side` int NOT NULL,
  `odd` decimal(5,2) NOT NULL,
  `status` int NOT NULL,
  PRIMARY KEY (`idB`),
  UNIQUE KEY `idB_UNIQUE` (`idB`),
  KEY `idU_idx` (`idU`),
  KEY `idE_idx` (`idE`),
  CONSTRAINT `idE2` FOREIGN KEY (`idE`) REFERENCES `Event` (`idE`) ON UPDATE CASCADE,
  CONSTRAINT `idU2` FOREIGN KEY (`idU`) REFERENCES `User` (`idU`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Bet`
--

LOCK TABLES `Bet` WRITE;
/*!40000 ALTER TABLE `Bet` DISABLE KEYS */;
/*!40000 ALTER TABLE `Bet` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Category`
--

DROP TABLE IF EXISTS `Category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Category` (
  `idC` int NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  PRIMARY KEY (`idC`),
  UNIQUE KEY `idC_UNIQUE` (`idC`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Category`
--

LOCK TABLES `Category` WRITE;
/*!40000 ALTER TABLE `Category` DISABLE KEYS */;
/*!40000 ALTER TABLE `Category` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Event`
--

DROP TABLE IF EXISTS `Event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Event` (
  `idE` int NOT NULL AUTO_INCREMENT,
  `title` varchar(45) NOT NULL,
  `description` varchar(255) NOT NULL,
  `idC` int NOT NULL,
  `dateBeg` datetime NOT NULL,
  `dateEnd` datetime NOT NULL,
  `oddNo` decimal(5,2) NOT NULL,
  `oddYes` decimal(5,2) NOT NULL,
  `status` int NOT NULL,
  `idCrea` int NOT NULL,
  `totalNo` int NOT NULL DEFAULT '0',
  `totalYes` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`idE`),
  UNIQUE KEY `idE_UNIQUE` (`idE`),
  KEY `idC_idx` (`idC`),
  KEY `idCrea_idx` (`idCrea`),
  CONSTRAINT `idC2` FOREIGN KEY (`idC`) REFERENCES `Category` (`idC`) ON UPDATE CASCADE,
  CONSTRAINT `idCrea` FOREIGN KEY (`idCrea`) REFERENCES `User` (`idU`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Event`
--

LOCK TABLES `Event` WRITE;
/*!40000 ALTER TABLE `Event` DISABLE KEYS */;
/*!40000 ALTER TABLE `Event` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `OldOdds`
--

DROP TABLE IF EXISTS `OldOdds`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `OldOdds` (
  `idO` int NOT NULL AUTO_INCREMENT,
  `idE` int NOT NULL,
  `oddNo` decimal(5,2) NOT NULL,
  `oddYes` decimal(5,2) NOT NULL,
  PRIMARY KEY (`idO`),
  UNIQUE KEY `idO_UNIQUE` (`idO`),
  KEY `idE_idx` (`idE`),
  CONSTRAINT `idE` FOREIGN KEY (`idE`) REFERENCES `Event` (`idE`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `OldOdds`
--

LOCK TABLES `OldOdds` WRITE;
/*!40000 ALTER TABLE `OldOdds` DISABLE KEYS */;
/*!40000 ALTER TABLE `OldOdds` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Transaction`
--

DROP TABLE IF EXISTS `Transaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Transaction` (
  `idT` int NOT NULL AUTO_INCREMENT,
  `idU` int NOT NULL,
  `amount` int NOT NULL,
  `type` int NOT NULL,
  `date` datetime NOT NULL,
  `description` varchar(45) DEFAULT NULL,
  `newBalance` int NOT NULL,
  PRIMARY KEY (`idT`),
  UNIQUE KEY `idT_UNIQUE` (`idT`),
  KEY `idU3_idx` (`idU`),
  CONSTRAINT `idU3` FOREIGN KEY (`idU`) REFERENCES `User` (`idU`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Transaction`
--

LOCK TABLES `Transaction` WRITE;
/*!40000 ALTER TABLE `Transaction` DISABLE KEYS */;
/*!40000 ALTER TABLE `Transaction` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `User`
--

DROP TABLE IF EXISTS `User`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `User` (
  `idU` int NOT NULL AUTO_INCREMENT,
  `username` varchar(45) NOT NULL,
  `email` varchar(45) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` int NOT NULL,
  `balance` int NOT NULL,
  `status` int NOT NULL,
  `name` varchar(45) NOT NULL,
  `surname` varchar(45) NOT NULL,
  PRIMARY KEY (`idU`),
  UNIQUE KEY `idU_UNIQUE` (`idU`),
  UNIQUE KEY `username_UNIQUE` (`username`),
  UNIQUE KEY `email_UNIQUE` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `User`
--

LOCK TABLES `User` WRITE;
/*!40000 ALTER TABLE `User` DISABLE KEYS */;
/*!40000 ALTER TABLE `User` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `User_Category`
--

DROP TABLE IF EXISTS `User_Category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `User_Category` (
  `idU` int NOT NULL,
  `idC` int NOT NULL,
  PRIMARY KEY (`idC`,`idU`),
  KEY `idU_idx` (`idU`),
  CONSTRAINT `idC` FOREIGN KEY (`idC`) REFERENCES `Category` (`idC`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `idU` FOREIGN KEY (`idU`) REFERENCES `User` (`idU`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `User_Category`
--

LOCK TABLES `User_Category` WRITE;
/*!40000 ALTER TABLE `User_Category` DISABLE KEYS */;
/*!40000 ALTER TABLE `User_Category` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-19 22:08:09
