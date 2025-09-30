import arcpy
import time
import os
from arcpy.sa import *

class SmallProjectsGISprocessing:
    def __init__(self, file_path):
        self.licenses = {
            "3D Analyst": arcpy.CheckExtension("3D"),
            "Spatial Analyst": arcpy.CheckExtension("Spatial")
        }
        licenses_unavailable = []

        # Check licenses and prompt user if they are not available
        for extension_name, status in self.licenses.items():
            if status != "Available":
                user_choice = raw_input("{} license is not available. Would you like to try checking out the license? (yes/no): ".format(extension_name))
                if user_choice.lower() == 'yes':
                    self.check_out_license(extension_name)
                    print "Checked out {} license successfully.".format(extension_name)
                else:
                    licenses_unavailable.append(extension_name)

        if len(licenses_unavailable) == len(self.licenses):
            print("Both 3D Analyst and Spatial Analyst licenses are not available. Some functionalities may not work.")

        self.file_path = file_path
        self.data = {}
        self.read_file()

    def check_out_license(self, extension_name):
        start_time = time.time()
        max_time = 60 * 60  # 1 hour
        while time.time() - start_time < max_time:
            if arcpy.CheckExtension(extension_name) == "Available":
                arcpy.CheckOutExtension(extension_name)
                print "Checked out {} license successfully.".format(extension_name)
                return
            else:
                print "{} license is unavailable. Trying again in 15 seconds.".format(extension_name)
            time.sleep(15)

    def read_file(self):
        try:
            with open(self.file_path, 'r') as file:
                for line in file:
                    self.process_line(line.strip())
        except IOError:
            print "File not found: {}".format(self.file_path)

    def process_line(self, line):
        if line.startswith("pathIn:"):
            self.data['pathIn'] = line.split("pathIn:")[1].strip()
        elif line.startswith("geodatabase_path:"):
            self.data['geodatabase_path'] = line.split("geodatabase_path:")[1].strip()
        elif line.startswith("input_raster:"):
            input_raster_template = line.split("input_raster:")[1].strip()
            geodatabase_path = self.data.get('geodatabase_path', '')
            self.data['input_raster'] = input_raster_template.replace('{}', geodatabase_path)
        elif line.startswith("min_x:"):
            self.data['min_x'] = float(line.split("min_x:")[1].strip())
        elif line.startswith("min_y:"):
            self.data['min_y'] = float(line.split("min_y:")[1].strip())
        elif line.startswith("max_x:"):
            self.data['max_x'] = float(line.split("max_x:")[1].strip())
        elif line.startswith("max_y:"):
            self.data['max_y'] = float(line.split("max_y:")[1].strip())
        elif line.startswith("pathrunoff:"):
            self.data['pathrunoff'] = line.split("pathrunoff:")[1].strip()
        elif line.startswith("project_shapefile_path:"):
            self.data['project_shapefile_path'] = line.split("project_shapefile_path:")[1].strip()
        elif line.startswith("GDA_shapefile_path:"):
            self.data['GDA_shapefile_path'] = line.split("GDA_shapefile_path:")[1].strip()
        elif line.startswith("EDA_shapefile_path:"):
            self.data['EDA_shapefile_path'] = line.split("EDA_shapefile_path:")[1].strip()

    def get_data(self):
        return self.data

    def extrdem(self):
        """
        Wrapper for the extrdem function, using data from the class.
        """
        pathIn = self.data.get('pathIn', '')
        input_raster = self.data.get('input_raster', '')
        min_x = self.data.get('min_x', 0)
        min_y = self.data.get('min_y', 0)
        max_x = self.data.get('max_x', 0)
        max_y = self.data.get('max_y', 0)
        clipped_raster = self._extrdem_internal(pathIn, input_raster, min_x, min_y, max_x, max_y)
        return clipped_raster

    def _extrdem_internal(self, pathIn, input_raster, min_x, min_y, max_x, max_y):
        """
        Extracts a portion of the DEM specified by the min and max coordinates.
        Saves the extracted DEM as TIFF and ASCII formats.
        """
        # Set up your environment
        env.workspace = pathIn
        env.overwriteOutput = True
        # Define your output paths
        clipped_raster = os.path.join(pathIn, "clipped_raster.tif")    # Clipped raster output
        ascii_output = os.path.join(pathIn, "output_ascii.asc")        # ASCII output
        rectangle_output = os.path.join(pathIn, "rectangle.shp")       # Rectangle output
        # Get the spatial reference of the input raster
        input_raster_desc = arcpy.Describe(input_raster)
        input_spatial_ref = input_raster_desc.spatialReference
        # Define the clipping geometry
        rectangle_geometry = arcpy.Polygon(arcpy.Array([arcpy.Point(min_x, min_y),
                                                        arcpy.Point(max_x, min_y),
                                                        arcpy.Point(max_x, max_y),
                                                        arcpy.Point(min_x, max_y)]),
                                           input_spatial_ref)

        # Save the rectangle geometry to a shapefile
        arcpy.CopyFeatures_management(rectangle_geometry, rectangle_output)
        # Clip the raster using the domain
        arcpy.Clip_management(input_raster, "#", clipped_raster, rectangle_geometry, "0", "ClippingGeometry")
        # Convert the clipped raster to ASCII format
        arcpy.RasterToASCII_conversion(clipped_raster, ascii_output)
        print("Raster clipped and saved as ASCII file successfully.")
        return clipped_raster
        
    def prepareRaster(self, clipped_raster_name="clipped_raster.tif"):
        """
        Wrapper for the prepareRaster function, using data from the class.
        """
        pathIn = self.data.get('pathIn', '')
        #clipped_raster_path = os.path.join(pathIn, "clipped_raster.tif")
        contour_interval = self.data.get('contour_interval', 1)
        accumulation_threshold = self.data.get('accumulation_threshold', 50)    
        # Construct the path for the clipped raster
        clipped_raster_path = os.path.join(pathIn, clipped_raster_name)      
        print("Contour Interval:", contour_interval)  # Debug print
        try:
            return self._prepareRaster_internal(pathIn, clipped_raster_path, contour_interval, accumulation_threshold)
        except Exception as e:
            print("Error in prepareRaster:", e)
            # Handle the error or re-raise
            raise      
        
    def _prepareRaster_internal(self, pathIn, clipped_raster_path, contour_interval, accumulation_threshold):
        """
        Processes DEM for watershed delineation including flow direction and accumulation.
        
        Parameters:
        - pathIn: The working directory path.
        - input_raster: Path to the clipped DEM raster.
        - contour_interval: Interval for contour generation.
        - accumulation_threshold: Threshold for defining streamlines.
        Returns:
        - Tuple of paths to flow direction raster and flow accumulation raster.
        """
        # Set environment settings
        env.workspace = pathIn
        env.overwriteOutput = True
        # Perform Fill
        filled_raster = os.path.join(pathIn, "filled_dem.tif")
        arcpy.gp.Fill_sa(clipped_raster_path, filled_raster)
        # Subtract filled DEM from clipped DEM
        depdepth1_raster = os.path.join(pathIn, "depdepth1.tif")
        clipped_raster1 = Raster(clipped_raster_path)
        depdepth1 = clipped_raster1 - Raster(filled_raster)
        depdepth1.save(depdepth1_raster)
        # Calculate Volume
        # cellSizeX = float(arcpy.GetRasterProperties_management(clipped_raster_path, "CELLSIZEX").getOutput(0))  # get cell size X
        # cellSizeY = float(arcpy.GetRasterProperties_management(clipped_raster_path, "CELLSIZEY").getOutput(0))  # get cell size Y
        # volume_raster = "volume1.tif"
        # arcpy.sa.Times(depdepth1, cellSizeX * cellSizeY).save(volume_raster)  # multiply depdepth1 with cell area
        flow_direction_raster = os.path.join(pathIn, "flow_direction.tif")
        arcpy.gp.FlowDirection_sa(filled_raster, flow_direction_raster)
        flow_accumulation_raster = os.path.join(pathIn, "flow_accumulation.tif")        
        arcpy.gp.FlowAccumulation_sa(flow_direction_raster, flow_accumulation_raster)
        # Generate contour lines at given intervals
        #contourz = os.path.join(pathIn, "contourz.shp")   
        arcpy.gp.Contour_sa(clipped_raster_path, "contourz.shp", contour_interval, "0")
        arcpy.gp.Contour_sa(filled_raster, "contourzfill.shp", contour_interval, "0")
        greaterThan = arcpy.sa.GreaterThan(flow_accumulation_raster, accumulation_threshold)
        con = arcpy.sa.Con(greaterThan, 1)
        streamlinesshp = os.path.join(pathIn, "streamlines.shp")  
        streamlines = arcpy.sa.StreamToFeature(con, flow_direction_raster, streamlinesshp, "NO_SIMPLIFY")
        print("Raster preparation completed.")
        # Return results for use in next function
        return flow_direction_raster, flow_accumulation_raster
        
    def prepareRasterWithStream(self, clipped_raster_name="clipped_raster.tif", stream_shapefile_name="streamtoburn.shp"):
        """
        Wrapper for the prepareRasterWithStream function, using data from the class.
        
        Parameters:
        - stream_shapefile_name: Optional. The name of the stream shapefile. Defaults to "example.shp".
        """
        pathIn = self.data.get('pathIn', '')
        contour_interval = self.data.get('contour_interval', 1)
        accumulation_threshold = self.data.get('accumulation_threshold', 50)
        # Construct the path for the stream_shapefile
        clipped_raster_path = os.path.join(pathIn, clipped_raster_name)
        stream_shapefile = os.path.join(pathIn, stream_shapefile_name)
        try:
            return self._prepareRasterWithStream_internal(pathIn, clipped_raster_path, contour_interval, stream_shapefile, accumulation_threshold)
        except Exception as e:
            print("Error in prepareRasterWithStream:", e)
            # Handle the error or re-raise
            raise
        
    def _prepareRasterWithStream_internal(self, pathIn, clipped_raster_path, contour_interval, stream_shapefile, accumulation_threshold):
        """
        Integrates a river network into DEM and processes it for watershed delineation.
        
        Parameters:
        - pathIn: The working directory path.
        - input_raster: Path to the clipped DEM raster.
        - contour_interval: Interval for contour generation.
        - stream_shapefile: Path to the river network shapefile.
        - accumulation_threshold: Threshold for defining streamlines.
        """
        # Set environment settings
        env.workspace = pathIn
        env.overwriteOutput = True
        # Convert stream vectors to raster with a value of 1
        stream_raster_temp = "stream_raster_temp.tif"
        stream_raster_file = "stream_raster.tif"
        # Check if field "Constant" exists, if not then add it
        field_names = [f.name for f in arcpy.ListFields(stream_shapefile)]
        if "Constant" not in field_names:
            arcpy.AddField_management(stream_shapefile, "Constant", "SHORT")
        arcpy.CalculateField_management(stream_shapefile, "Constant", "1", "PYTHON")
        arcpy.FeatureToRaster_conversion(stream_shapefile, "Constant", stream_raster_temp, arcpy.GetRasterProperties_management(clipped_raster_path, "CELLSIZEX").getOutput(0))
        # Replace NoData values in the raster with 0
        stream_raster = arcpy.sa.Con(arcpy.sa.IsNull(stream_raster_temp), 0, stream_raster_temp)
        stream_raster.save(stream_raster_file)
        # Subtract an arbitrary value (10) from DEM wherever stream is 1
        dem_raster = Raster(clipped_raster_path)
        dem_with_stream = Con(stream_raster == 1, dem_raster - 10, dem_raster)
        dem_with_stream_file = "dem_with_stream.tif"
        dem_with_stream.save(dem_with_stream_file)
        # Perform Fill
        filled_raster = "filled_dem.tif"
        arcpy.gp.Fill_sa(dem_with_stream_file, filled_raster)
        depdepth1_raster = "depdepth1.tif"
        depdepth1 = dem_raster - Raster(filled_raster)
        depdepth1.save(depdepth1_raster)
        flow_direction_raster = "flow_direction.tif"
        arcpy.gp.FlowDirection_sa(filled_raster, flow_direction_raster)
        flow_accumulation_raster = "flow_accumulation.tif"
        arcpy.gp.FlowAccumulation_sa(flow_direction_raster, flow_accumulation_raster)
        # Generate contour lines at contour_interval
        contourz = "contourz.shp"
        arcpy.gp.Contour_sa(clipped_raster_path, contourz, contour_interval, "0")
        # Generating streamlines
        greaterThan = arcpy.sa.GreaterThan(flow_accumulation_raster, accumulation_threshold)
        con = arcpy.sa.Con(greaterThan,1)
        streamlines = arcpy.sa.StreamToFeature(con, flow_direction_raster, "streamlinesedited.shp", "NO_SIMPLIFY")
        print("PrepareRasterWithStream function executed successfully.")
        return flow_direction_raster, flow_accumulation_raster, dem_with_stream_file        
        
    def createPourPointAndDelineateWatershed(self, pour_point_x, pour_point_y, snap_distance, output_name):
        """
        Wrapper for the createPourPointAndDelineateWatershed function, using data from the class.
        
        Parameters:
        - pour_point_x, pour_point_y: X and Y coordinates of the pour point.
        - snap_distance: The distance within which to snap the pour point to the nearest cell of high accumulation.
        - output_name: Name for the output watershed files.
        """
        pathIn = self.data.get('pathIn', '')
        flow_direction_raster = os.path.join(pathIn, "flow_direction.tif")
        flow_accumulation_raster = os.path.join(pathIn, "flow_accumulation.tif")
        try:
            return self._createPourPointAndDelineateWatershed_internal(pathIn, pour_point_x, pour_point_y, snap_distance, flow_direction_raster, flow_accumulation_raster, output_name)
        except Exception as e:
            print("Error in createPourPointAndDelineateWatershed:", e)
            # Handle the error or re-raise
            raise

    def _createPourPointAndDelineateWatershed_internal(self, pathIn, pour_point_x, pour_point_y, snap_distance, flow_direction_raster, flow_accumulation_raster, output_name):
        """
        Creates pour points and delineates the watershed based on the flow direction and accumulation rasters.
    
        Parameters:
        - pathIn: The working directory path.
        - pour_point_x, pour_point_y: X and Y coordinates of the pour point.
        - snap_distance: The distance within which to snap the pour point to the nearest cell of high accumulation.
        - flow_direction_raster: Path to the flow direction raster.
        - flow_accumulation_raster: Path to the flow accumulation raster.
        - output_name: Name for the output watershed files.
        Outputs:
        - Watershed shapefile delineated based on the specified pour point.
        """
        env.workspace = pathIn
        env.overwriteOutput = True
        # Set spatial reference
        spatial_ref = arcpy.SpatialReference(2957)
        # Create a pour point feature class
        pour_point_fc = "PourPoints.shp"
        arcpy.CreateFeatureclass_management(pathIn, pour_point_fc, "POINT", spatial_reference=spatial_ref)
        arcpy.AddField_management(pour_point_fc, "ID", "LONG")
        cursor = arcpy.da.InsertCursor(pour_point_fc, ["ID", "SHAPE@XY"])
        cursor.insertRow([1, (pour_point_x, pour_point_y)])
        del cursor
        snap_pour_point_raster = output_name + "_snapped_pour_point.tif"
        arcpy.gp.SnapPourPoint_sa(pour_point_fc, flow_accumulation_raster, snap_pour_point_raster, snap_distance)
        # Create a feature class from the snapped pour point
        snapped_pour_point_fc = output_name + "_snapped_pour_point.shp"
        arcpy.RasterToPoint_conversion(snap_pour_point_raster, snapped_pour_point_fc)
        watershed_raster = output_name + "_GDA.tif"
        arcpy.gp.Watershed_sa(flow_direction_raster, snapped_pour_point_fc, watershed_raster)
        # Convert watershed raster to shapefile
        watershed_shapefile = output_name + "_GDA.shp"
        arcpy.RasterToPolygon_conversion(watershed_raster, watershed_shapefile, "NO_SIMPLIFY", "VALUE")
        # Add "areashape" field and calculate area for the watershed polygon
        arcpy.AddField_management(watershed_shapefile, "areashape", "DOUBLE")
        arcpy.CalculateField_management(watershed_shapefile, "areashape", "!shape.area@SQUAREKILOMETERS!", "PYTHON")
        #Copy the watershed shapefile with a new name (with extension 'EDA')
        eda_shapefile = output_name + "_EDA.shp"
        arcpy.CopyFeatures_management(watershed_shapefile, eda_shapefile)
        print("createPourPointAndDelineateWatershed function executed successfully.")
    
    def appendProjectShapefiles(self, Projcurrent, EDAcurrent, GDAcurrent):
        """
        Appends the current project's shapefiles to the respective all-project shapefiles.

        Parameters:
        - Projcurrent: Name of the current project's general shapefile.
        - EDAcurrent: Name of the current project's EDA shapefile.
        - GDAcurrent: Name of the current project's GDA shapefile.
        """
        pathIn = self.data.get('pathIn', '')
        project_shapefile_path = self.data.get('project_shapefile_path', '')
        GDA_shapefile_path = self.data.get('GDA_shapefile_path', '')
        EDA_shapefile_path = self.data.get('EDA_shapefile_path', '')
        # Append current project to project list layer
        curProj = os.path.join(pathIn, Projcurrent)
        fieldMappings = arcpy.FieldMappings()
        arcpy.Append_management(curProj, project_shapefile_path, "NO_TEST", fieldMappings)
        # Append current project GDA to the all GDA list layer
        curGDA = os.path.join(pathIn, GDAcurrent)
        arcpy.Append_management(curGDA, GDA_shapefile_path, "NO_TEST", fieldMappings)
        # Append current project EDA to the all EDA list layer
        curEDA = os.path.join(pathIn, EDAcurrent)
        arcpy.Append_management(curEDA, EDA_shapefile_path, "NO_TEST", fieldMappings)
        print("Project shapefiles appended successfully.")

    def runoffIndex(self, inZoneData, zoneField, outTable):
        """
        Calculates the runoff index based on the given zone data.
        Parameters:
        - inZoneData: Name of the input zone data shapefile.
        - zoneField: The field to use for zone calculations.
        - outTable: Name for the output table.
        """
        pathIn = self.data.get('pathIn', '')
        pathrunoff = self.data.get('pathrunoff', '') 
        # Set environment settings
        arcpy.env.workspace = pathIn
        arcpy.env.overwriteOutput = True
        # Set local variables
        inValueRaster70 = os.path.join(pathrunoff, "urunoff_70p.tif")
        inValueRaster50 = os.path.join(pathrunoff, "urunoff_50p.tif")
        # Run ZonalStatisticsAsTable for the first raster and save it as outTable
        arcpy.gp.ZonalStatisticsAsTable_sa(inZoneData, zoneField, inValueRaster70, outTable, "DATA", "SUM")
        # Add a new field to outTable and calculate its values based on 'SUM' field
        arcpy.AddField_management(outTable, "SUM_70", "DOUBLE")
        arcpy.CalculateField_management(outTable, "SUM_70", "!SUM! * 0.0081", "PYTHON")
        # Run ZonalStatisticsAsTable for the second raster and save it as a temporary table
        tempTable = "temp.dbf"
        arcpy.gp.ZonalStatisticsAsTable_sa(inZoneData, zoneField, inValueRaster50, tempTable, "DATA", "SUM")
        # Add a new field to tempTable and calculate its values based on 'SUM' field
        arcpy.AddField_management(tempTable, "SUM_50", "DOUBLE")
        arcpy.CalculateField_management(tempTable, "SUM_50", "!SUM! * 0.0081", "PYTHON")
        # Join the tempTable to the outTable based on zoneField
        arcpy.JoinField_management(outTable, zoneField, tempTable, zoneField, ["SUM_50"])
        print("Runoff index calculations completed successfully.")
