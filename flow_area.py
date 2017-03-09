#-------------------------------------------------------------------------------
# Name:        IntersectZones.py
# Purpose:
# Author:      Research Planning, Inc.
#
# Created:     12/04/2016
# Copyright:   (c) Research Planning, Inc. 2016
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import os, sys, arcpy, traceback, math
from arcpy import env


def find_overlaps(input_features1, input_features2):

    for row in arcpy.da.SearchCursor(input_features, ('OID@', 'SHAPE@')):
        for row2 in arcpy.da.SearchCursor(input_features, ('OID@', 'SHAPE@')):
            if row2[1].overlaps(row[1]):
                print '{0} overlaps {1}'.format(str(row2[0]), str(row[0]))

def add_subtract_radians(theta):
    return (theta + 1.57079632679, theta - 1.57079632679)

def distance(x1, y1, x2, y2):
    return float(math.pow(((math.pow((x2-x1),2)) + (math.pow((y2 - y1),2))),.5))

def cart_to_polar(xy1, xy2):
    try:
        x1, y1, x2, y2 = float(xy1[0]), float(xy1[1]), float(xy2[0]), float(xy2[1])
        xdistance, ydistance = x2 - x1, y2 - y1
        distance = math.pow(((math.pow((x2 - x1),2)) + (math.pow((y2 - y1),2))),.5)
        if xdistance == 0:
            if y2 > y1:
                theta = math.pi/2
            else:
                theta = (3*math.pi)/2
        elif ydistance == 0:
            if x2 > x1:
                theta = 0
            else:
                theta = math.pi
        else:
            theta = math.atan(ydistance/xdistance)
            if xdistance > 0 and ydistance < 0:
                theta = 2*math.pi + theta
            if xdistance < 0 and ydistance > 0:
                theta = math.pi + theta
            if xdistance < 0 and ydistance < 0:
                theta = math.pi + theta
        return [distance, theta]
    except:
        print"      Cutline - Error in CartesianToPolar()"

def polar_to_cart(polarcoords):
    r = polarcoords[0]
    theta = polarcoords[1]
    x = r * math.cos(theta)
    y = r * math.sin(theta)
    return [x, y]

def make_perpendicular(input_lines, distance, fcname, start):
    #Get the input line files geometry as a python list.
    desc = arcpy.Describe(input_lines)
    shapefieldname = desc.ShapeFieldName
    rows = arcpy.SearchCursor(input_lines)
    listofpointgeometry = []
    for row in rows:
        feat = row.getValue(shapefieldname)
        partnum = 0
        partcount = feat.partCount
        thisrecordsgeometry = []
        while partnum < partcount:
            part = feat.getPart(partnum)
            pnt = part.next()
            pntcount = 0
            while pnt:
                thetuple = [pnt.X, pnt.Y]
                thisrecordsgeometry.append(thetuple)
                pnt = part.next()
                pntcount += 1
            partnum += 1
        startnode = [thisrecordsgeometry[0][0], thisrecordsgeometry[0][1]]
        if start:
            startnode = [thisrecordsgeometry[0][0], thisrecordsgeometry[0][1]]
            endnode = [thisrecordsgeometry[1][0], thisrecordsgeometry[1][1]]
        else:
            startnode = [thisrecordsgeometry[-2][0], thisrecordsgeometry[-2][1]]
            endnode = [thisrecordsgeometry[-1][0], thisrecordsgeometry[-1][1]]
        listofpointgeometry.append([startnode,endnode])

    #Create the feature class to store the new geometry....
    featureList = []
    array = arcpy.Array()
    pnt = arcpy.Point()

    for pt in listofpointgeometry:
        startx = pt[0][0]
        starty = pt[0][1]
        endx = pt[1][0]
        endy = pt[1][1]
        #get a theta
        polarcoor = cart_to_polar((startx,starty), (endx,endy))

        #Add and subtract the 90 degrees in radians from the line...
        ends = add_subtract_radians(polarcoor[1])
        firstend = polar_to_cart((float(distance),float(ends[0])))
        secondend = polar_to_cart((float(distance),float(ends[1])))

        if start:
            firstx2 = startx + firstend[0]
            firsty2 = starty + firstend[1]
            secondx2 = startx + secondend[0]
            secondy2 = starty + secondend[1]
            midx = startx
            midy = starty
        else:
            firstx2 = endx + firstend[0]
            firsty2 = endy + firstend[1]
            secondx2 = endx + secondend[0]
            secondy2 = endy + secondend[1]
            midx = startx
            midy = starty

        pnt.X, pnt.Y = firstx2 , firsty2
        array.add(pnt)
        pnt.X, pnt.Y = midx , midy
        array.add(pnt)
        pnt.X, pnt.Y = secondx2 , secondy2
        array.add(pnt)
        polyline = arcpy.Polyline(array)
        array.removeAll()
        featureList.append(polyline)
    arcpy.CopyFeatures_management(featureList, fcname)



def flow_area(input_nhd_area_polys, input_flow_lines, input_upstr_pts, input_dnstr_pts, input_all_flow_lines):
    try:
        # Script arguments and setup workspace
        arcpy.env.qualifiedFieldNames = False
        desc = arcpy.Describe(input_nhd_area_polys)
        arcpy.env.workspace = desc.path
        arcpy.AddMessage("Input workspace: "+str(desc.path))

        # Fill holes
        ## Do we need to do this?  Not sure...

        # Determine appropriate cutline width
        ## placeholder - use 500m as default below

        # Construct perpedicular cutlines for flowlines that are 1.) within open water polygons and 2.) that end at an upstream or downstream endpoint
        ## Uses 500m as placeholder cutline width - will need to refactor if using unique pwidths for each polygon, but maybe not nessecary
        ## Need to add in checks to see length of end line segment and use average if very small, or check to see if endpoitn on vertex and average
        arcpy.SelectLayerByAttribute_management(input_flow_lines, "CLEAR_SELECTION")
        arcpy.SelectLayerByLocation_management(in_layer=input_flow_lines, overlap_type="WITHIN", select_features=input_nhd_area_polys, search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.SelectLayerByLocation_management(in_layer=input_flow_lines, overlap_type="BOUNDARY_TOUCHES", select_features=input_upstr_pts, search_distance="", selection_type="SUBSET_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.AddMessage("Making upstream perpendicular cutlines...")
        make_perpendicular(input_flow_lines, 500, "TEST_swpt_cutline_upstrm", True)
        arcpy.SelectLayerByLocation_management(in_layer=input_flow_lines, overlap_type="WITHIN", select_features=input_nhd_area_polys, search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.SelectLayerByLocation_management(in_layer=input_flow_lines, overlap_type="BOUNDARY_TOUCHES", select_features=input_dnstr_pts, search_distance="", selection_type="SUBSET_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.AddMessage("Making downstream perpendicular cutlines...")
        make_perpendicular(input_flow_lines, 500, "TEST_swpt_cutline_dwnstrm", False)

        # Crack NHD open water polygons with cutlines and trim with "WITHIN" reselect
        ## To Do
        ## arcpy.SelectLayerByLocation_management(in_layer=input_nhd_area_polys, overlap_type="CONTAINS", select_features=input_flow_lines, search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        ## arcpy.CopyFeatures_management(input_nhd_area_polys, "swpt_ndhar6mi_fl")

        # Identify NHD open water polygons containing flowlines from multiple DWUNIQUE values, or flowlines from one or more DWUNIQUE values and a non-upstream-downstream flowline
        ## this select should take place with the cutline-trimmed version

        ## NEED TO ADD some stuff here to only select correct polygons...  currently to performs Thiessen with all flowlines inside NHD open water polygons
        # Clip flowlines by NHD open water polygons
        arcpy.SelectLayerByLocation_management(in_layer=input_nhd_area_polys, overlap_type="INTERSECT", select_features=input_flow_lines, search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.SelectLayerByLocation_management(in_layer=input_flow_lines, overlap_type="WITHIN", select_features=input_nhd_area_polys, search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.AddMessage("Clipping upstream/downstream flowlines by NHD area polygons...")
        arcpy.Clip_analysis(in_features=input_flow_lines, clip_features=input_nhd_area_polys, out_feature_class="TEST_swpt_all_fl_nhdarclip")
        arcpy.AddMessage("Clipping all flowlines by NHD area polygons...")
        arcpy.Clip_analysis(in_features=input_all_flow_lines, clip_features=input_nhd_area_polys, out_feature_class="TEST_swpt_nhdfl6mi_nhdarclip")

        arcpy.MakeFeatureLayer_management(in_features="TEST_swpt_all_fl_nhdarclip",out_layer="TEST_swpt_all_fl_nhdarclip")
        arcpy.MakeFeatureLayer_management(in_features="TEST_swpt_nhdfl6mi_nhdarclip",out_layer="TEST_swpt_nhdfl6mi_nhdarclip")

        arcpy.AddMessage("Converting vertices to points...")
        arcpy.FeatureVerticesToPoints_management(in_features="TEST_swpt_all_fl_nhdarclip", out_feature_class="TEST_swpt_all_fl_nhdarclip_vert", point_location="ALL")
        arcpy.FeatureVerticesToPoints_management(in_features="TEST_swpt_nhdfl6mi_nhdarclip", out_feature_class="TEST_swpt_nhdfl6mi_nhdarclip_vert", point_location="ALL")
        arcpy.MakeFeatureLayer_management(in_features="TEST_swpt_all_fl_nhdarclip_vert",out_layer="TEST_swpt_all_fl_nhdarclip_vert")
        arcpy.MakeFeatureLayer_management(in_features="TEST_swpt_nhdfl6mi_nhdarclip_vert",out_layer="TEST_swpt_nhdfl6mi_nhdarclip_vert")
        arcpy.SelectLayerByLocation_management(in_layer="TEST_swpt_all_fl_nhdarclip_vert", overlap_type="INTERSECT", select_features="TEST_swpt_all_fl_nhdarclip_vert", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="INVERT")
        arcpy.Merge_management(inputs="TEST_swpt_all_fl_nhdarclip_vert;TEST_swpt_nhdfl6mi_nhdarclip_vert", output="TEST_swpt_vert_all")

        # Convert vertices from ALL flowlines inside such open water polygons and generate Thiessen Polygons
        ## To Do - TEST HERE

        # Crack only such open water polygons with thiessen polygon boundaries
        ## To Do

        # Merge Thiessen-cracked open water polygons with non-Thiessen-cracked
        ## To Do

        # Spatial join (one-to-many) flowlines to merged open water polygons
        ## To Do

        # Dissolve on DWUNIQUE, FCode, and Permanent_Identifier
        ## To Do


        pass

    except arcpy.ExecuteError:
        # Get the geoprocessing error messages
        msgs = arcpy.GetMessage(0)
        msgs += arcpy.GetMessages(2)

        # Return gp error messages for use with a script tool
        arcpy.AddError(msgs)
        # Print gp error messages for use in Python/PythonWin
        print msgs

    except:
        # Get the traceback object
        tb = sys.exc_info()[2]
        tbinfo = traceback.format_tb(tb)[0]
        # Concatenate information together concerning the error into a
        # message string
        pymsg = tbinfo + "\n" + str(sys.exc_type)+ ": " + str(sys.exc_value)

        # Return python error messages for use with a script tool
        arcpy.AddError(pymsg)

        # Print Python error messages for use in Python/PythonWin
        print pymsg

if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i) for i in range(arcpy.GetArgumentCount()))
    flow_area(*argv)








# perpLines = []
# fc = "line"
# sr = arcpy.Describe(fc).spatialReference
# perpLineSpacing = 1000
# perpLineLength = 1000
# with arcpy.da.SearchCursor(fc,"SHAPE@",spatial_reference=sr) as cursor:
#      for row in cursor:
#          for part in row[0]: # part = a line array
#              for i in range(len(part)):
#                  if i==0: # first vertex
#                      perpLineCounter = 0
#                  else:
#                      dy = part[i].Y - part[i-1].Y
#                      dx = part[i].X - part[i-1].X
#                      segmentAngle = math.degrees(math.atan2(dy,dx))
#                      segmentLength = math.sqrt(math.pow(dy,2)+math.pow(dx,2))
#                      linesOnSegment = int(segmentLength/perpLineSpacing)
#                      for line in range(linesOnSegment+1):
#                          point = row[0].positionAlongLine(perpLineCounter * perpLineSpacing)
#                          left = arcpy.Point(point.centroid.X - (math.cos(math.radians(segmentAngle-90))*perpLineLength), point.centroid.Y - (math.sin(math.radians(segmentAngle-90))*perpLineLength))
#                          right = arcpy.Point(point.centroid.X + (math.cos(math.radians(segmentAngle-90))*perpLineLength), point.centroid.Y + (math.sin(math.radians(segmentAngle-90))*perpLineLength))
#                          perpLines.append(arcpy.Polyline(arcpy.Array([left,right]),sr))
#                          perpLineCounter += 1
#  arcpy.CopyFeatures_management(perpLines ,r'in_memory\lines')
