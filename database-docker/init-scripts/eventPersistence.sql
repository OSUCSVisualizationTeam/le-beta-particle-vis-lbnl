SET FOREIGN_KEY_CHECKS=0;
SET AUTOCOMMIT = 0;

CREATE SCHEMA IF NOT EXISTS `lbnlfits` DEFAULT CHARACTER SET utf8 ;
USE `lbnlfits` ;

DROP TABLE IF EXISTS `fits_files` ;
CREATE TABLE IF NOT EXISTS `fits_files`(
  `fitsID` INT NOT NULL AUTO_INCREMENT,
  `fileName` VARCHAR(255) NOT NULL,
  `date` DATETIME NOT NULL,
  `min` FLOAT NOT NULL,
  `max` FLOAT NOT NULL,
  `exposureTime` FLOAT NOT NULL,
  PRIMARY KEY (`fitsID`)
);

DROP TABLE IF EXISTS `clusters` ;
CREATE TABLE IF NOT EXISTS `clusters` (
  `fitsFile` INT NOT NULL,
  `clusterID` INT NOT NULL AUTO_INCREMENT,
  `hdu_id` INT NOT NULL,
  `box_top` INT NOT NULL,
  `box_left` INT NOT NULL,
  `box_bottom` INT NOT NULL,
  `box_right` INT NOT NULL,
  `data` BLOB,
  `totalEnergy` FLOAT NOT NULL,
  `sigmaX` FLOAT NOT NULL,
  `sigmaY` FLOAT NOT NULL,
  `classification` VARCHAR(255),
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
    IN filename VARCHAR(255),
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
    INSERT INTO fits_files(fileName, date, min, max, exposureTime)
    VALUES (filename, date, min, max, exposureTime);

    SET fitsID = LAST_INSERT_ID();

    COMMIT;
END //

DELIMITER ;

DROP PROCEDURE IF EXISTS insert_cluster;
DELIMITER //

CREATE PROCEDURE insert_cluster(
    IN fitsFile INT,
    IN HDU INT,
    IN box_top INT,
    IN box_left INT,
    IN box_bottom INT,
    IN box_right INT,
    IN data BLOB,
    IN totalEnergy FLOAT,
    IN sigmaX FLOAT,
    IN sigmaY FLOAT,
    IN classification VARCHAR(255),
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
    INSERT INTO clusters(fitsFile, hdu_id, box_top, box_left, box_bottom, box_right, data, totalEnergy, sigmaX, sigmaY, classification, pixelCount)
    VALUES (fitsFile, HDU, box_top, box_left, box_bottom, box_right, data, totalEnergy, sigmaX, sigmaY, classification, pixelCount);

    SET clusterID = LAST_INSERT_ID();

    COMMIT;
END //

DELIMITER ;

DROP PROCEDURE IF EXISTS insert_classifications;
DELIMITER //

CREATE PROCEDURE insert_classifications(
    IN classification VARCHAR(255),
    IN in_clusterID INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
    END;
    START TRANSACTION;
    UPDATE clusters
    SET classification = classification
    WHERE clusterID = in_clusterID;
    COMMIT;
END //

DROP VIEW IF EXISTS v_tritium_candidates;

CREATE VIEW v_tritium_candidates as
SELECT * FROM clusters 
WHERE classification = "tritium"
ORDER BY classification DESC;

SET FOREIGN_KEY_CHECKS=1;
