#-------------------------------------------------------------------------------
# Name:        flow_area.py
# Purpose:
# Author:      Research Planning, Inc.
#
# Created:     3/04/2017
# Copyright:   (c) Research Planning, Inc. 2017
#
#-------------------------------------------------------------------------------

import os, sys, arcpy, traceback, math
from arcpy import env

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

def remove_self_intersects(input_features, intersect_points, id_field, output_features):
    # Function to remove portions of features from supplied feature class that 1.) intersect, 2.) are not identical, 3.) have the same ID field, and 4.) do not overlap a supplied set of points.
    #
    # ARGUMENTS:
    # input_features:       Feature class or layer containing features to check for intersections
    # intersect_points:     Feature class or layer containing points to check against. Portions of intersecting features will be retained if they intersect with these points.
    # id_field:             Attribute field containing ID field to check against.  Only intersecting features with same ID will be split and checked against point feature class.
    # output_features:      Feature class output name

    desc = arcpy.Describe(input_features)
    spatialRef = desc.spatialReference
    workspace = desc.path
    arcpy.CreateFeatureclass_management(workspace, output_features, "POLYLINE", input_features,"","", spatialRef)
    with arcpy.da.InsertCursor(output_features, ['SHAPE@', 'DWUNIQUE']) as cursor:
        for row in arcpy.da.SearchCursor(input_features, ('SHAPE@', str(id_field))):
            val = True
            cutlines = []
            for row2 in arcpy.da.SearchCursor(input_features, ('SHAPE@', str(id_field))):
                if not row2[0].disjoint(row[0]):
                    if not row2[0].equals(row[0]) and row[1] == row2[1]:
                        arcpy.AddMessage( '  Cutline {0} overlaps {1}.  Splitting...'.format(str(row2[1]), str(row[1])))
                        cutlines = row[0].cut(row2[0])
                        val = False
            if val:
                for point in arcpy.da.SearchCursor(intersect_points, ('SHAPE@')):
                    if not point[0].disjoint(row[0]):
                        cursor.insertRow([row[0],row[1]])
            else:
                for cutline in cutlines:
                    for point in arcpy.da.SearchCursor(intersect_points, ('SHAPE@')):
                        if not point[0].disjoint(cutline):
                            cursor.insertRow([cutline,row[1]])

def make_perpendicular(input_lines, distance, output_features, start):
    # Function to generate perpendicular cutlines at start or stop of polyline features, and copy to newly created feature class.
    #
    # ARGUMENTS:
    # input_lines:          Feature class or layer containing lines for which to generate perpendicular cutlines.  Presumes DWUNIQUE exists as text field
    # distance:             Distance in horizontal units of input feature class
    # output_features:      Feature class output name
    # start:                Boolean indicating whether to generate perpendicular cutline at beginning/start or end/stop point of line. True indicates beginning/start, False indicates end/stop

    # Setup environment and get spatial reference of input
    desc = arcpy.Describe(input_lines)
    spatialRef = desc.spatialReference
    workspace = desc.path

    # Get the input line features geometry and DWUNIQUE as a python list.
    rows = arcpy.da.SearchCursor(input_lines, ('SHAPE@', 'DWUNIQUE'))
    listofpointgeometry = []
    listofids = []
    for row in rows:
        feat = row[0]
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
        if start:
            startnode = [thisrecordsgeometry[0][0], thisrecordsgeometry[0][1]]
            endnode = [thisrecordsgeometry[1][0], thisrecordsgeometry[1][1]]
        else:
            startnode = [thisrecordsgeometry[-2][0], thisrecordsgeometry[-2][1]]
            endnode = [thisrecordsgeometry[-1][0], thisrecordsgeometry[-1][1]]
        listofpointgeometry.append([startnode,endnode])
        listofids.append(str(row[1]))

    # Create the feature class to store the new geometry....
    arcpy.CreateFeatureclass_management(workspace, output_features, "POLYLINE", "","","", spatialRef)
    arcpy.AddField_management(output_features, "DWUNIQUE", "TEXT", 50)

    # Cursor through points, make cutlines and add features to destination feature class
    array = arcpy.Array()
    pnt = arcpy.Point()
    with arcpy.da.InsertCursor(output_features, ['SHAPE@', 'DWUNIQUE']) as cursor:
        for pt in listofpointgeometry:
            lind = listofpointgeometry.index(pt)
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
                midx = endx
                midy = endy
            pnt.X, pnt.Y = firstx2 , firsty2
            array.add(pnt)
            pnt.X, pnt.Y = midx , midy
            array.add(pnt)
            pnt.X, pnt.Y = secondx2 , secondy2
            array.add(pnt)
            polyline = arcpy.Polyline(array)
            cursor.insertRow([polyline,listofids[lind]])
            array.removeAll()
    del cursor



def flow_area(input_nhd_area_polys, input_flow_lines, input_upstr_pts, input_dnstr_pts, input_all_flow_lines, thiessen):
    try:
        # ARGUMENTS:
        # input_nhd_area_polys: Feature layer containing NHD area polgyons that may contain upstream-downstream flowlines
        # input_flow_lines:     Feature layer containing upstream-downstream flowlines that may intersect NHD area polgyons
        # input_upstr_pts:      Feature layer containing upstream termination points for upstream-downstream flowlines that may intersect NHD area polgyons
        # input_dnstr_pts:      Feature layer containing downstream termination points for upstream-downstream flowlines that may intersect NHD area polgyons
        # input_all_flow_lines: Feature layer containing all flowlines (including non-upstream-downstream) that may intersect NHD area polgyons
        # thiessen:             Boolean indicating whether to preserve thiessen-derived breaks when in conflict with cutline-derived. True preserves thiessen-derived, False preserves cutline-derived

        # Setup workspace and environment
        arcpy.env.qualifiedFieldNames = False
        arcpy.env.overwriteOutput = True
        desc = arcpy.Describe(input_nhd_area_polys)
        arcpy.env.workspace = desc.path
        arcpy.AddMessage("  Input workspace: "+str(desc.path))

        # Extract only Artificial paths from input flowlines
        arcpy.AddMessage("  Filtering flowlines to extract only artificial paths...")
        arcpy.SelectLayerByAttribute_management(input_flow_lines, "CLEAR_SELECTION")
        arcpy.SelectLayerByAttribute_management(in_layer_or_view=input_flow_lines, selection_type="NEW_SELECTION", where_clause="FCode = 55800")
        arcpy.CopyFeatures_management(input_flow_lines, "pf_swpt_all_fl_filt")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_all_fl_filt",out_layer="pf_swpt_all_fl_filt")
        arcpy.SelectLayerByAttribute_management(input_all_flow_lines, "CLEAR_SELECTION")
        arcpy.SelectLayerByAttribute_management(in_layer_or_view=input_all_flow_lines, selection_type="NEW_SELECTION", where_clause="FCode = 55800")
        arcpy.CopyFeatures_management(input_all_flow_lines, "pf_swpt_nhdfl6mi_filt")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdfl6mi_filt",out_layer="pf_swpt_nhdfl6mi_filt")

        # Merge upstream and downstream flowline endpoints
        arcpy.AddMessage("  Merging flowline endpoints...")
        arcpy.Merge_management(inputs=str(input_upstr_pts)+";"+str(input_dnstr_pts), output="pf_swpt_splitpnt_ends", field_mappings="")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_splitpnt_ends",out_layer="pf_swpt_splitpnt_ends")

        # Dissolve all NHD Area polygons and remove islands
        arcpy.SelectLayerByAttribute_management(input_nhd_area_polys, "CLEAR_SELECTION")
        arcpy.SelectLayerByLocation_management(in_layer=input_nhd_area_polys, overlap_type="INTERSECT", select_features="pf_swpt_all_fl_filt", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.AddMessage("  Dissolving all NHD area polygons that intersect upstream/downstream flowlines...")
        arcpy.Dissolve_management(in_features=input_nhd_area_polys, out_feature_class="pf_swpt_nhdar6mi_diss", dissolve_field="", statistics_fields="", multi_part="SINGLE_PART", unsplit_lines="DISSOLVE_LINES")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdar6mi_diss",out_layer="pf_swpt_nhdar6mi_diss")
        arcpy.AddMessage("  Filling holes in NHD area polygons that intersect upstream/downstream flowlines...")
        arcpy.EliminatePolygonPart_management(in_features="pf_swpt_nhdar6mi_diss", out_feature_class="pf_swpt_nhdar6mi_elim",condition="AREA_AND_PERCENT", part_area="1000000 SquareMeters", part_area_percent="99.0", part_option="CONTAINED_ONLY")

        # Construct perpendicular cutlines for flowlines that are 1.) within open water polygons and 2.) that end at an upstream or downstream endpoint
        arcpy.SelectLayerByAttribute_management(input_flow_lines, "CLEAR_SELECTION")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_all_fl_filt", overlap_type="WITHIN", select_features="pf_swpt_nhdar6mi_diss", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_all_fl_filt", overlap_type="BOUNDARY_TOUCHES", select_features=input_upstr_pts, search_distance="", selection_type="SUBSET_SELECTION", invert_spatial_relationship="NOT_INVERT")
        make_perpendicular("pf_swpt_all_fl_filt", 2000, "pf_swpt_cutline_upstrm", True)

        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_all_fl_filt", overlap_type="WITHIN", select_features="pf_swpt_nhdar6mi_diss", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_all_fl_filt", overlap_type="BOUNDARY_TOUCHES", select_features=input_dnstr_pts, search_distance="", selection_type="SUBSET_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.AddMessage("  Making downstream perpendicular cutlines...")
        make_perpendicular("pf_swpt_all_fl_filt", 2000, "pf_swpt_cutline_dwnstrm", False)
        arcpy.SelectLayerByAttribute_management("pf_swpt_all_fl_filt", "CLEAR_SELECTION")

        # Get only parts of cutlines we want
        arcpy.AddMessage("  Extracting correct portion of cutlines...")
        arcpy.Merge_management(inputs="pf_swpt_cutline_dwnstrm;pf_swpt_cutline_upstrm", output="pf_swpt_cutlines_all")
        arcpy.Clip_analysis(in_features="pf_swpt_cutlines_all", clip_features="pf_swpt_nhdar6mi_elim", out_feature_class="pf_swpt_cutlines_clip")
        arcpy.MultipartToSinglepart_management(in_features="pf_swpt_cutlines_clip", out_feature_class="pf_swpt_cutlines_clip_mult")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_cutlines_clip_mult",out_layer="pf_swpt_cutlines_clip_mult")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_cutlines_clip_mult", overlap_type="INTERSECT", select_features="pf_swpt_splitpnt_ends", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.CopyFeatures_management("pf_swpt_cutlines_clip_mult", "pf_swpt_cutlines_clip_mult_ends")
        arcpy.AddMessage("  Deleting unneeded portions of intersecting cutlines...")
        remove_self_intersects("pf_swpt_cutlines_clip_mult_ends", "pf_swpt_splitpnt_ends", "DWUNIQUE", "pf_swpt_cutlines_filt")

       # Crack island-removed NHD open water polygons with cutlines and trim
        arcpy.AddMessage("  Cracking and trimming NHD area polygons with perpendicular cutlines...")
        arcpy.FeatureToPolygon_management(in_features="pf_swpt_nhdar6mi_elim;pf_swpt_cutlines_filt", out_feature_class="pf_swpt_nhdar_allcut", cluster_tolerance="", attributes="ATTRIBUTES", label_features="")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdar_allcut",out_layer="pf_swpt_nhdar_allcut")
        arcpy.SelectLayerByAttribute_management("pf_swpt_all_fl_filt", "CLEAR_SELECTION")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdar_allcut", overlap_type="CROSSED_BY_THE_OUTLINE_OF", select_features="pf_swpt_all_fl_filt", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdar_allcut", overlap_type="CONTAINS", select_features="pf_swpt_all_fl_filt", search_distance="", selection_type="ADD_TO_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.CopyFeatures_management("pf_swpt_nhdar_allcut", "pf_swpt_nhdar_cut")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdar_cut",out_layer="pf_swpt_nhdar_cut")

        # Clip flowlines by NHD open water polygons
        arcpy.AddMessage("  Clipping upstream/downstream flowlines by NHD area polygons...")
        arcpy.Clip_analysis(in_features="pf_swpt_all_fl_filt", clip_features="pf_swpt_nhdar_cut", out_feature_class="pf_swpt_all_fl_filt_nhdarclip")
        arcpy.AddMessage("  Clipping all flowlines by NHD area polygons...")
        arcpy.Clip_analysis(in_features="pf_swpt_nhdfl6mi_filt", clip_features="pf_swpt_nhdar_cut", out_feature_class="pf_swpt_nhdfl6mi_nhdarclip")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_all_fl_filt_nhdarclip",out_layer="pf_swpt_all_fl_filt_nhdarclip")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdfl6mi_nhdarclip",out_layer="pf_swpt_nhdfl6mi_nhdarclip")

        # Convert vertices from ALL flowlines inside such open water polygons, merge, and discard duplicated vertices from non-upstream-downstream flowlines, if present
        arcpy.AddMessage("  Densifying flowlines...")
        arcpy.Densify_edit(in_features="pf_swpt_all_fl_filt_nhdarclip", densification_method="DISTANCE", distance="10 Meters", max_deviation="0.1 Meters", max_angle="10")
        arcpy.Densify_edit(in_features="pf_swpt_nhdfl6mi_nhdarclip", densification_method="DISTANCE", distance="10 Meters", max_deviation="0.1 Meters", max_angle="10")
        arcpy.AddMessage("  Converting vertices to points...")
        arcpy.FeatureVerticesToPoints_management(in_features="pf_swpt_all_fl_filt_nhdarclip", out_feature_class="pf_swpt_all_fl_nhdarclip_vert", point_location="ALL")
        arcpy.FeatureVerticesToPoints_management(in_features="pf_swpt_nhdfl6mi_nhdarclip", out_feature_class="pf_swpt_nhdfl6mi_nhdarclip_vert", point_location="ALL")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_all_fl_nhdarclip_vert",out_layer="pf_swpt_all_fl_nhdarclip_vert")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdfl6mi_nhdarclip_vert",out_layer="pf_swpt_nhdfl6mi_nhdarclip_vert")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdfl6mi_nhdarclip_vert", overlap_type="INTERSECT", select_features="pf_swpt_all_fl_nhdarclip_vert", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="INVERT")
        arcpy.Merge_management(inputs="pf_swpt_all_fl_nhdarclip_vert;pf_swpt_nhdfl6mi_nhdarclip_vert", output="pf_swpt_vert_all")

        # Generate Thiessen polygons
        arcpy.AddMessage("  Generating Thiessen polygons...")
        arcpy.env.extent = arcpy.Describe("pf_swpt_nhdar_cut").extent
        arcpy.CreateThiessenPolygons_analysis(in_features="pf_swpt_vert_all", out_feature_class="pf_swpt_vert_all_th", fields_to_copy="ONLY_FID")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_vert_all_th",out_layer="pf_swpt_vert_all_th")
        arcpy.env.extent = "MAXOF"

        # Crack open water polygons with thiessen polygon boundaries
        arcpy.AddMessage("  Cracking NHD area polygons with Thiessen polygons...")
        arcpy.Identity_analysis(in_features="pf_swpt_nhdar_cut", identity_features="pf_swpt_vert_all_th", out_feature_class="pf_swpt_nhdar_cut_th", join_attributes="ONLY_FID", cluster_tolerance="", relationship="NO_RELATIONSHIPS")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdar_cut_th",out_layer="pf_swpt_nhdar_cut_th")

        # Check for and merge orphaned polygons that no longer intersect a flowline
        arcpy.AddMessage("  Merging orphaned polygons...")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdar_cut_th", overlap_type="INTERSECT", select_features="pf_swpt_nhdfl6mi_filt", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="INVERT")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdar_cut_th", overlap_type="SHARE_A_LINE_SEGMENT_WITH", select_features="pf_swpt_nhdar_cut_th", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        if str(thiessen).lower() == 'true': # THIS OPTION PRESERVES THIESSEN POLYS WHEN IN CONFLICT
            arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdar_cut_th", overlap_type="INTERSECT", select_features="pf_swpt_splitpnt_ends", search_distance="", selection_type="REMOVE_FROM_SELECTION", invert_spatial_relationship="NOT_INVERT")
            arcpy.Dissolve_management(in_features="pf_swpt_nhdar_cut_th", out_feature_class="pf_swpt_nhdar_cut_th_orphans", dissolve_field="FID_pf_swpt_vert_all_th", statistics_fields="", multi_part="MULTI_PART", unsplit_lines="DISSOLVE_LINES")
        else: # THIS OPTION PRESERVES CUTLINE POLYS WHEN IN CONFLICT
            arcpy.Dissolve_management(in_features="pf_swpt_nhdar_cut_th", out_feature_class="pf_swpt_nhdar_cut_th_orphans", dissolve_field="FID_pf_swpt_nhdar_cut", statistics_fields="", multi_part="MULTI_PART", unsplit_lines="DISSOLVE_LINES")

        arcpy.SelectLayerByAttribute_management(in_layer_or_view="pf_swpt_nhdar_cut_th", selection_type="SWITCH_SELECTION", where_clause="")
        arcpy.Merge_management(inputs="pf_swpt_nhdar_cut_th;pf_swpt_nhdar_cut_th_orphans", output="pf_swpt_nhdar_cut_th_merged", field_mappings="")

        # Spatial join (one-to-many) flowlines to merged open water polygons
        arcpy.AddMessage("  Joining cracked NHD area polygons to upstream/downstream flowlines...")
        arcpy.SelectLayerByAttribute_management("pf_swpt_all_fl_filt", "CLEAR_SELECTION")
        arcpy.SpatialJoin_analysis(target_features="pf_swpt_nhdar_cut_th_merged", join_features="pf_swpt_all_fl_filt", out_feature_class="pf_swpt_nhdar_cut_th_merged_join", join_operation="JOIN_ONE_TO_MANY", join_type="KEEP_COMMON", match_option="CROSSED_BY_THE_OUTLINE_OF", search_radius="", distance_field_name="")

        # Dissolve on DWUNIQUE and clip using dissolved NHD open water polygons
        arcpy.AddMessage("  Dissolving cracked NHD area polygons by DWUNIQUE and clipping to make final output...")
        arcpy.Dissolve_management(in_features="pf_swpt_nhdar_cut_th_merged_join", out_feature_class="pf_swpt_nhdar_cut_th_merged_join_diss", dissolve_field="DWUNIQUE", statistics_fields="", multi_part="SINGLE_PART", unsplit_lines="DISSOLVE_LINES")
        arcpy.MakeFeatureLayer_management(in_features="pf_swpt_nhdar_cut_th_merged_join_diss",out_layer="pf_swpt_nhdar_cut_th_merged_join_diss")
        arcpy.SelectLayerByLocation_management(in_layer="pf_swpt_nhdar_cut_th_merged_join_diss", overlap_type="INTERSECT", select_features="pf_swpt_all_fl_filt", search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
        arcpy.Dissolve_management(in_features="pf_swpt_nhdar_cut_th_merged_join_diss", out_feature_class="pf_swpt_nhdar_all_fl", dissolve_field="DWUNIQUE", statistics_fields="", multi_part="MULTI_PART", unsplit_lines="DISSOLVE_LINES")
        arcpy.Clip_analysis(in_features="pf_swpt_nhdar_all_fl", clip_features="pf_swpt_nhdar6mi_diss", out_feature_class="pf_swpt_nhdar_all_fl_clip", cluster_tolerance="")

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
