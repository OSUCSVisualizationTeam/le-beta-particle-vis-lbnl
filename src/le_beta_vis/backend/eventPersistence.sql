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
  `cnn_classification` FLOAT,
  `bdt_classification` FLOAT,
  `nrg_classification` FLOAT,
  `pixelCount` INT NOT NULL,
  INDEX `fk_fits_files` (`fitsFile` ASC) VISIBLE,
  INDEX `idx_total_energy` (`totalEnergy` ASC) VISIBLE,
  INDEX `idx_sigma_x` (`sigmaX` ASC) VISIBLE,
  INDEX `idx_sigma_y` (`sigmaY` ASC) VISIBLE,
  INDEX `idx_pixel_count` (`pixelCount` ASC) VISIBLE,
  INDEX `idx_classification` (`classification` ASC) VISIBLE,
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
    IN in_fitsFile INT,
    IN in_HDU INT,
    IN in_box_top INT,
    IN in_box_left INT,
    IN in_box_bottom INT,
    IN in_box_right INT,
    IN in_data BLOB,
    IN in_totalEnergy FLOAT,
    IN in_sigmaX FLOAT,
    IN in_sigmaY FLOAT,
    IN in_classification VARCHAR(255),
    IN in_cnnclassification FLOAT,
    IN in_bdtclassification FLOAT,
    IN in_nrgclassification FLOAT,
    IN in_pixelCount INT,
    OUT out_clusterID INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET out_clusterID = -99;
    END;
    START TRANSACTION;
    INSERT INTO clusters(fitsFile, hdu_id, box_top, box_left, box_bottom, 
                        box_right, data, totalEnergy, sigmaX, sigmaY, classification,
                        cnn_classification, bdt_classification, nrg_classification, pixelCount)
    VALUES (in_fitsFile, in_HDU, in_box_top, in_box_left, in_box_bottom, 
            in_box_right, in_data, in_totalEnergy, in_sigmaX, 
            in_sigmaY, in_classification, in_cnnclassification,
            in_bdtclassification, in_nrgclassification, in_pixelCount);

    SET out_clusterID = LAST_INSERT_ID();

    COMMIT;
END //

DELIMITER ;

DROP PROCEDURE IF EXISTS insert_classifications;
DELIMITER //

CREATE PROCEDURE insert_classifications(
    IN in_classification VARCHAR(255),
    IN in_clusterID INT,
    OUT out_rows_updated INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET out_rows_updated = -1;
    END;
    START TRANSACTION;
    UPDATE clusters
    SET classification = in_classification
    WHERE clusterID = in_clusterID;
    SET out_rows_updated = ROW_COUNT();
    COMMIT;
END //

DROP VIEW IF EXISTS v_tritium_candidates;

CREATE VIEW v_tritium_candidates as
SELECT * FROM clusters
WHERE classification = "tritium"
ORDER BY classification DESC;

SET FOREIGN_KEY_CHECKS=1;
