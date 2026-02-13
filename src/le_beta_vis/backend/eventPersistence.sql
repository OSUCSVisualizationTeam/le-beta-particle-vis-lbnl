SET FOREIGN_KEY_CHECKS=0;
SET AUTOCOMMIT = 0;

CREATE SCHEMA IF NOT EXISTS `lbnlfits` DEFAULT CHARACTER SET utf8 ;
USE `lbnlfits` ;

DROP TABLE IF EXISTS `fits_files` ;
CREATE TABLE IF NOT EXISTS `fits_files`(
  `fitsID` INT NOT NULL,
  `date` DATETIME NOT NULL,
  `min` FLOAT NOT NULL,
  `max` FLOAT NOT NULL,
  `exposureTime` FLOAT NOT NULL,
  PRIMARY KEY (`fitsID`)
);

DROP TABLE IF EXISTS `clusters` ;
CREATE TABLE IF NOT EXISTS `clusters` (
  `fitsFile` INT NOT NULL,
  `clusterID` INT NOT NULL,
  `data` BLOB NOT NULL,
  `totalEnergy` FLOAT NOT NULL,
  `sigmaX` FLOAT NOT NULL,
  `sigmaY` FLOAT NOT NULL,
  `classificationCNN` FLOAT NULL,
  `classificationNRG` FLOAT NULL,
  `classificationBDT` FLOAT NULL,
  `pixelCount` INT NOT NULL,
  INDEX `fk_fits_files` (`fitsFile` ASC) VISIBLE,
  PRIMARY KEY (`clusterID`),
  CONSTRAINT `fits_files`
    FOREIGN KEY (`fitsFile`)
    REFERENCES `fits_files` (`fitsID`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION);

DROP PROCEDURE IF EXISTS insert_fits;
DELIMITER //

CREATE PROCEDURE insert_fits(
    IN date DATETIME,
    IN min FLOAT,
    IN max FLOAT,
    IN exposureTime FLOAT,
    OUT fitsID INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET fitsID = -99;
    END;
    START TRANSACTION;
    INSERT INTO fits_files(date, min, max, exposureTime)
    VALUES (date, min, max, exposureTime);

    SET fitsID = LAST_INSERT_ID();

    COMMIT;
END //

DELIMITER ;

DROP PROCEDURE IF EXISTS insert_cluster;
DELIMITER //

CREATE PROCEDURE insert_cluster(
    IN fitsFile INT,
    IN data BLOB,
    IN totalEnergy FLOAT,
    IN sigmaX FLOAT,
    IN sigmaY FLOAT,
    IN classificationCNN FLOAT,
    IN classificationNRG FLOAT,
    IN classificationBDT FLOAT,
    IN pixelCount INT,
    OUT clusterID INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET clusterID = -99;
    END;
    START TRANSACTION;
    INSERT INTO clusters(fitsFile, data, totalEnergy, sigmaX, sigmaY, classificationCNN,
                        classificationNRG, classificationBDT, pixelCount)
    VALUES (fitsFile, data, totalEnergy, sigmaX, sigmaY, classificationCNN,
            classificationNRG, classificationBDT, pixelCount);

    SET clusterID = LAST_INSERT_ID();

    COMMIT;
END //

DELIMITER ;

DROP VIEW IF EXISTS v_tritium_candidates;

CREATE VIEW v_tritium_candidates as
SELECT * FROM clusters
WHERE classificationCNN > 0.75 or classificationNRG > 0.75 or classificationBDT > 0.75
ORDER BY classificationCNN DESC, classificationNRG DESC, classificationBDT DESC;

SET FOREIGN_KEY_CHECKS=1;