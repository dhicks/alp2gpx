#!/usr/bin/env python3
'''
Licensed under the GNU GENERAL PUBLIC LICENSE (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

https://www.gnu.org/licenses/gpl-3.0.html

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS-IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
 

Based on flifplip's apq2gpx (https://github.com/phkehl/apq2gpx).

This job is an attempt to port flipflip's original code
in Perl to Python.
'''

import sys
from struct import *
from datetime import datetime
import base64
import xml.etree.ElementTree as ET
import io
import os
import argparse

class alp2gpx(object):
    inputfile, outputfile = None, None
    fileVersion, headerSize = None, None
    metadata, waypoints, segments = None, None, None 
    
    def __init__(self, inputfile, outputfile):
        self.inputfile = open(inputfile, "rb")
        self.outputfile = outputfile
        
        ext = os.path.splitext(inputfile)[1]
        if ext.lower() == '.trk':
            self.parse_trk()
        elif ext.lower() == '.ldk':
            self.parse_ldk()
        else:
            print('File not supported yet')
        
    
    def _get_int(self):
        result = self.inputfile.read(4)
        return  unpack('>l', result)[0]
    
    def _get_double(self):
        result = self.inputfile.read(8)
        return  unpack('>d', result)[0]
    
    def _get_coordinate(self):
        result = self._get_int() * 1e-7;
        return result
    
    def _get_double(self):
        result = self.inputfile.read(8)
        return  unpack('>d', result)[0]
    
    def _get_long(self):
        result = self.inputfile.read(8)
        return  unpack('>q', result)[0]
     
    def _get_timestamp(self):
        result = self._get_long() * 1e-3;
        return result
    
    def _get_string(self, size):
        result = self.inputfile.read(size)
        return result.decode('UTF-8')
        
    def _get_raw(self, size):
        value = self.inputfile.read(size)
        #result = base64.b64encode(value)
        return(value)
    
    def _get_int_raw(self):
        size = self._get_int()
        value = self.inputfile.read(size)
        result = base64.b64encode(value)
        return result
    
    def _get_bool(self):
        result = self.inputfile.read(1)
        return unpack('c', result)[0]
    
    def _get_pointer(self):
        result = self.inputfile.read(8)
        return unpack('>Q', result)[0]
    
    
    def _get_height(self):
        result = self._get_int()
        if result ==  -999999999:
            return None
        else:
            result *= 1e-3
        return result
    
    def _get_accuracy(self):
        return self._get_int()
    
    def _get_pressure(self):
        result = self._get_int()
        if result ==  999999999:
            return None
        else:
            result *= 1e-3
        return result        
    
    def _get_metadata(self, fileVersion):
        result = {}
        num_of_metaentries = self._get_int()
        for entry in range(num_of_metaentries):
            name_len = self._get_int()
            name = self._get_string(name_len)
            data_len = self._get_int()
            if data_len == -1:  data = self._get_bool()
            if data_len == -2:  data = self._get_long()
            if data_len == -3:  data = self._get_double()
            if data_len == -4:  data = self._get_int_raw()
            if data_len >= 0:  data = self._get_string(data_len)
            result[name] = data
        if fileVersion == 3:
            nmeta_ext = self._get_int()

        return result
    
    def _get_location(self, segmentVersion):
        size = self._get_int()
        lon = self._get_coordinate()
        lat = self._get_coordinate()
        if segmentVersion <= 3: 
            alt = self._get_height()
            ts = self._get_timestamp()
            
            acc,bar = None, None
            
            if size > 20:
                acc = self._get_accuracy()
            if size > 24:
                bar = self._get_pressure()
        
        elif segmentVersion == 4:
            size = size - 8     # count used items
            acc,bar = None, None
            while size > 0:
                # read name of data (e=elevation, ...)
                name = self._get_string(1)
                if name == "e":
                    # elevation
                    alt = self._get_height()
                    size = size - 5
                    # print("Altitude" , alt)
                    continue
                if name == "t":
                    # timestamp
                    ts = self._get_timestamp()
                    size = size - 9
                    # print("Time" , ts)
                    continue
                if name == "a":
                    # accuracy
                    acc = self._get_accuracy()
                    size = size - 5
                    # print("accuracy" , acc)
                    continue
                if name == "p":
                    # pressure
                    bar = self._get_pressure()
                    size = size - 5
                    # print("pressure" , bar)
                    continue
                
        else:
            print("Location format error")
            exit()
            
        result = { 'lat': lat, 'lon': lon, 'alt': alt, 'ts': ts, 'acc': acc, 'bar': bar}
        return result
    
    
    def _get_segment(self, segmentVersion):
        if segmentVersion < 3:
            self._get_int()
        else:
            meta = self._get_metadata(segmentVersion)
            if segmentVersion == 4:
                self._get_int() # skip unknown int
                self._get_int() # skip unknown int
        
        nlocations = self._get_int()
#         print("Nb locations:" , nlocations)
        result = []
        for n in range(nlocations):
            location = self._get_location(segmentVersion)
            result.append(location)
        return result
            
    def _get_segments(self, segmentVersion):
        num_segments = self._get_int()
#         print("Nb segments:" , num_segments)
        results = []
        for s in range(num_segments):
            segment = self._get_segment(segmentVersion)
            results.append(segment)
        return results
            
            
    def _get_waypoints(self):
        num_waypoints = self._get_int()
#         print("Nb waypoints:" , num_waypoints)
        result = []
        for wp in range(num_waypoints):
            meta = self._get_metadata(self.fileVersion)
            location = self._get_location()
            result.append({'meta': meta, 'location': location})
        return result
        
    def _get_additional_data(self, offset):
        data = ''
        magic_number = self._get_int()   
        size = self._get_long()
        add_offset = self._get_pointer()
        add_data = self._get_raw(size)
        data += add_data
        if add_offset:
            moreData = self._get_additional_data(add_offset)
            data += moreData
        return(data)
            
    def _get_node_data(self, node):
        data = ''
        self.inputfile.seek(node['offset'])
        magic_number = self._get_int()   
        flags = self._get_int()
        total_size = self._get_long()
        size = self._get_long()        
        add_offset = self._get_pointer()    
        data += self._get_raw(size)
        
        if add_offset:
            data += self._get_additional_data(add_offset)
        
        return data
        
    def _get_node(self, offset, path=None, uuid=None):
        # {Node}
        # - int magic number of the node (0x00015555)
        # - int flags
        # - pointer {Metadata} position of node metadata
        # - double reserved
        # - {NodeEntries} entries of the nod
        
        self.inputfile.seek(offset)
        magig_number_of_the_node = self._get_int()
        flags  = self._get_int()
        metadata_pointer = self._get_pointer()
        node_entries = self._get_long()
        
        self.inputfile.seek(metadata_pointer+0x20)
        metadata = self._get_metadata(2)
        self.inputfile.seek(node_entries)
         
        if path and not uuid:
            path = '/'
        elif uuid:
            if metadata.get('name', ''):
                path = metadata.get('name')+'/'
            else:
                path = '%08X' % uuid
      
        node_entries_magic = self._get_int()
        
        if node_entries_magic == 0x00025555:
            n_total = self._get_int()
            n_child = self._get_int()
            n_data = self._get_int()
            add_offset = self._get_pointer()
            n_empty = n_total - n_child - n_data;
        elif node_entries_magic == 0x00045555:
            n_child = self._get_int()
            n_data = self._get_int()
            n_empty = 0
        else:
            return None
        
        child_entries = []
        for child in range(n_child):
            offset = self._get_pointer()
            uuid = self._get_int()
            child_entries.append({'uuid': uuid, 'offset':offset})
            
            
        self.inputfile.seek(self.inputfile.tell() + n_empty * (8+4))
        data_entries = []
        for x in range(n_data):
            offset = self._get_pointer()
            uuid = self._get_int()
            data_entries.append({'offset': offset, 'uuid': uuid, 'path': path})
            
        node = []
        for entry in child_entries:
            child = self._get_node(entry['offset'], path, entry['uuid']);
            node.append(child)

        for entry in data_entries:
            data = self._get_node_data(entry)
            file_type = unpack('i', data[:4])[0]
            file_data = data[1:]
            
            '''
            FOR FUTURE REFERENCE
            type_map = ({'101': 'wpt', '102': 'set', '103':  'rte', '104': 'trk', '105':  'are' });
            type_str = type_map[file_type]
            '''
            
            if file_type == 104:
                bytes = io.BytesIO(file_data)
                self.inputfile = bytes
                self.inputfile.seek(0)
                self.parse_trk()
            else:
                '''
                NOT SUPPORTED FILE TYPE
                FOR NOW
                '''
                pass
              
            
    def total_track_time(self):
        self.inputfile.seek(60)
        result = self._get_long()
        return result        
        
    def total_track_elevation_gain(self):
        self.inputfile.seek(52)
        result = self._get_double()
        return result        
        
    def total_track_length_due_to_elevation(self):
        self.inputfile.seek(44)
        result = self._get_double()
        return result
         
    def total_track_length(self):
        self.inputfile.seek(36)
        result = self._get_double()
        return result
    
    ## TODO: datetime.utcfromtimestamp() vs. datetime.fromtimestamp()
    def time_of_first_location(self):
        if self.fileVersion <= 3:
            self.inputfile.seek(28)
            result = datetime.fromtimestamp(self._get_timestamp())
        else:
            result = datetime.fromtimestamp(self.sumary.get('dte') * 1e-3)
        return result
    
    def latitude_of_first_location(self):
        self.inputfile.seek(24)
        result = self._get_coordinate()
        return result
    
    def longitude_of_first_location(self):
        self.inputfile.seek(20)
        result = self._get_coordinate()
        return result
    
    def number_of_waypoints(self):
        self.inputfile.seek(16)
        result = self._get_int()     
        return(result)
    
    def number_of_segments(self):
        self.inputfile.seek(12)
        result = self._get_int()     
        return(result)
     
    def number_of_locations(self):
        self.inputfile.seek(8)
        result = self._get_int()     
        return(result)
    
        
    def check_version(self):
        self.inputfile.seek(0)
        file_version = self._get_int()
        if file_version > 3:
            file_version = 4
        header_size  = self._get_int()          
        return (file_version, header_size);
    
    def write_xml(self):
        '''
        <?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.0">
            <metadata>
            <desc>description</desc>
            <link href="" />
            <time>2020-04-18T13:26:36Z</time>
            </metadata>
            <wpt lat="46.57638889" lon="8.89263889">
                <ele>2372</ele>
                <name>LAGORETICO</name>
            </wpt>
            <trk><name>Example gpx</name><number>1</number><trkseg>
                <trkpt lat="46.57608333" lon="8.89241667"><ele>2376</ele><time>2007-10-14T10:09:57Z</time></trkpt>
                <trkpt lat="46.57619444" lon="8.89252778"><ele>2375</ele><time>2007-10-14T10:10:52Z</time></trkpt>
                <trkpt lat="46.57641667" lon="8.89266667"><ele>2372</ele><time>2007-10-14T10:12:39Z</time></trkpt>
                <trkpt lat="46.57650000" lon="8.89280556"><ele>2373</ele><time>2007-10-14T10:13:12Z</time></trkpt>
                <trkpt lat="46.57638889" lon="8.89302778"><ele>2374</ele><time>2007-10-14T10:13:20Z</time></trkpt>
                <trkpt lat="46.57652778" lon="8.89322222"><ele>2375</ele><time>2007-10-14T10:13:48Z</time></trkpt>
                <trkpt lat="46.57661111" lon="8.89344444"><ele>2376</ele><time>2007-10-14T10:14:08Z</time></trkpt>
            </trkseg></trk>
        </gpx>
        '''
        tsdebut = self.time_of_first_location()
        if not self.metadata.get('name'):
            name = tsdebut.strftime("%Y-%m-%d %H:%M:%S")
            filename = tsdebut.strftime("%y-%m-%d")
        else:
            name = tsdebut.strftime("%Y-%m-%d %H:%M:%S") + ' ' + self.metadata.get('name')
            filename = tsdebut.strftime("%y-%m-%d") + ' ' + self.metadata.get('name')

            # suppress characters not permitted in filename
            for i in [';', ':', '!', "*", '/', '\\', '.', ','] :
                filename = filename.replace(i, '-')

            # suppress trailing space
            filename = filename.strip()
            
        # print('Name:', name)
        
        root = ET.Element('gpx', xmlns="http://www.topografix.com/GPX/1/1", version = '1.1', creator="Alp2gpx" )
        root.text = '\n'
        tree = ET.ElementTree(root)
        metadata = ET.SubElement(root, 'metadata')
        metadata.text = '\n'
        metadata.tail = '\n'
        desc = ET.SubElement(metadata, 'desc')
        desc.text = name
        desc.tail = '\n'
        link = ET.SubElement(metadata, 'link', href='https://github.com/jachetto/alp2gpx')
        link.tail = '\n'
        
        for wp in self.waypoints:
            wpt = ET.SubElement(root, 'wpt', lat = '%s' % wp['location']['lat'], lon = '%s' % wp['location']['lon'] )
            node = ET.SubElement(wpt, 'ele')
            node.text = '%s' % wp['location']['alt']
            node = ET.SubElement(wpt, 'name')
            node.text = wp['meta']['name']
            
        for s in self.segments:
            trk = ET.SubElement(root, 'trk')
            trk.text = '\n'
            trk.tail = '\n'
            tname = ET.SubElement(trk, 'name')
            tname.text = name
            tname.tail = '\n'

            trkseg = ET.SubElement(trk, 'trkseg')
            trkseg.text = '\n'
            trkseg.tail = '\n'
            for p in s:
                trkpt = ET.SubElement(trkseg, 'trkpt', lat = '%s' % p['lat'], lon = '%s' % p['lon'] )
                trkpt.text = '\n'
                trkpt.tail = '\n'
                node = ET.SubElement(trkpt, 'ele')
                node.text = '%s' % p['alt']                
                node.tail = '\n'
                d = datetime.utcfromtimestamp(int(p['ts']))
                tz = d.strftime("%Y-%m-%dT%H:%M:%SZ")
                node = ET.SubElement(trkpt, 'time')
                node.text = tz
                node.tail = '\n'
                
        tree.write(self.outputfile, encoding='utf-8', xml_declaration=True)
        
        
    def parse_trk(self):
        # version 3 (version 2 is the same but uses a different {Metadata} and {Segments} struct
        # - int         file version
        # - int         header size (size of data to before {Metadata}
        # - int         number of locations
        # - int         number of segments
        # - int         number of waypoints
        # - coordinate  longitude of first location
        # - coordinate  latitude of first location
        # - timestamp   time of first location
        # - double      total track length (in m)
        # - double      total track length due to elevation changes (in m)
        # - double      total track elevation gain (in m)
        # - long        total track time (in s)
        # - {Metadata}  (version 2)
        # - {Waypoints}
        # - {Segments}  (version 2)        
        
        # version 4 
        # - int         ?? constant = 50 50 0e 01 ???
        # - int         offset of first byte after {Metadata}
        # - {summary}   strcuture with same format as metadata,
        #               contain first lon, lat, timestamp
        # - int         ?? constant = 00 00 00 03 ???
        # - int         ?? constant = ff ff ff ff ???
        # - {Metadata}  (version 2)
        # - int         ?? 
        # - int         ?? constant = ff ff ff ff ???
        # - {Waypoints}
        # - {Segments}  (version 4), the format of location structure changed.
        
        '''
        JUST FOR API REFERENCE
        number_of_locations = self.number_of_locations()
        number_of_segments = self.number_of_segments()
        number_of_waypoints = self.number_of_waypoints()
        longitude_of_first_location = self.longitude_of_first_location()
        latitude_of_first_location = self.latitude_of_first_location()
        time_of_first_location = self.time_of_first_location()
        total_track_length = self.total_track_length()
        total_track_length_due_to_elevation = self.total_track_length_due_to_elevation()
        total_track_elevation_gain = self.total_track_elevation_gain()
        total_track_time = self.total_track_time()
        '''
        
        (self.fileVersion, self.headerSize)= self.check_version()    
#         print("Version:", self.fileVersion)
        
        if self.fileVersion <= 3:
            self.inputfile.seek(self.headerSize+8)
            self.metadata = self._get_metadata(self.fileVersion)
            self.waypoints = self._get_waypoints()
            self.segments = self._get_segments(self.fileVersion)
            self.write_xml()
        else:            
            # read sumary data
            self.inputfile.seek(8)
            self.sumary = self._get_metadata(self.fileVersion)
            # print("time of first loc 2:", self.sumary.get('dte'))

            # skip 2 unknown int
            x1 = self._get_int() 
            x2 = self._get_int()  

            # read metatdata
            self.metadata = self._get_metadata(self.fileVersion)
#             print(self.metadata.get('name'))
            
            # skip 2 unknown int
            x1 = self._get_int()  
            x2 = self._get_int()  

            # read waypoints (not tested with waypoints in file)
            self.waypoints = self._get_waypoints()

            # read track
            self.segments = self._get_segments(self.fileVersion)

            self.write_xml()
        #self.inputfile.seek(0)
   
    
    def parse_ldk(self):
        # - int       application specific magic number
        # - int       archive version
        # - pointer   {Node} position of the root node (always with list entries)
        # - double    reserved
        # - double    reserved
        # - double    reserved
        # - double    reserved            
        self.inputfile.seek(0)
        application_specific_magic_number = self._get_int()
        archive_version = self._get_int()
        position_of_the_root_node = self._get_pointer()
        res1, res2, res3, res4 = self._get_double(), self._get_double(), self._get_double(), self._get_double()
        
        root_node = self._get_node(position_of_the_root_node)
        
        pass
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("input", help = "input file to convert (.trk, etc.)")
    parser.add_argument("-o", "--output", 
                        default = None,  # Handled after parser.parse_args()
                        help = "output base name (default input file path and base name)")

    args = parser.parse_args()
    if args.output is None:
        args.output = '%s.gpx' % os.path.splitext(args.input)[0]

    
    q = alp2gpx(args.input, args.output)
